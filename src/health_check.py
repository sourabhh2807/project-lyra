"""
health_check.py — Daily system health monitor.
Opens GitHub Issues automatically if critical checks fail.
"""
import os, json, glob, sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def check():
    issues = []
    now    = datetime.now(timezone.utc)

    # 1. Check each channel has published in last 72h
    channel_map_path = os.path.join(ROOT, "data/channel_map.json")
    if os.path.exists(channel_map_path):
        with open(channel_map_path) as f:
            channel_map = json.load(f)

        for ch in channel_map["channels"]:
            if ch["status"] != "active":
                continue
            slot  = ch["slot"]
            pattern = os.path.join(ROOT, "execution/publish_logs/*.json")
            last_upload = None
            for path in glob.glob(pattern):
                try:
                    with open(path) as f:
                        entry = json.load(f)
                    if entry.get("slot") == slot:
                        ts = datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
                        if last_upload is None or ts > last_upload:
                            last_upload = ts
                except Exception:
                    pass

            if last_upload is None:
                issues.append(f"WARN: Slot {slot} ({ch['name']}) has NEVER uploaded")
            elif (now - last_upload).total_seconds() > 72 * 3600:
                hours_ago = int((now - last_upload).total_seconds() / 3600)
                issues.append(f"WARN: Slot {slot} ({ch['name']}) last upload was {hours_ago}h ago")

    # 2. Check error log for recent critical errors
    error_log_path = os.path.join(ROOT, "data/error_log.json")
    if os.path.exists(error_log_path):
        with open(error_log_path) as f:
            errors = json.load(f)
        recent_errors = [
            e for e in errors
            if (now - datetime.fromisoformat(
                e.get("ts","2000-01-01T00:00:00+00:00").replace("Z","+00:00")
            )).total_seconds() < 24 * 3600
        ]
        if len(recent_errors) > 5:
            issues.append(f"ERROR: {len(recent_errors)} errors in last 24h")

    # 3. Check genome DB size
    db_path = os.path.join(ROOT, "data/genome.db")
    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        if size_mb > 90:
            issues.append(f"WARN: genome.db is {size_mb:.1f}MB (approaching 100MB limit)")

    # 4. Check research freshness
    research_pattern = os.path.join(ROOT, "research/processed/topic_candidates/*.json")
    candidates = glob.glob(research_pattern)
    if len(candidates) < 3:
        issues.append(f"WARN: Only {len(candidates)} topic candidates available — research may be stalled")

    # Save health report
    report = {
        "ts":            now.isoformat(),
        "status":        "unhealthy" if issues else "healthy",
        "issues":        issues,
        "checks_passed": 4 - len(issues),
        "checks_total":  4,
    }
    report_path = os.path.join(ROOT, "data/health_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Print to stdout (visible in GitHub Actions logs)
    print(f"\n{'='*50}")
    print(f"LYRA HEALTH CHECK: {report['status'].upper()}")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M')} UTC")
    if issues:
        print("\nISSUES:")
        for issue in issues:
            print(f"  • {issue}")
    else:
        print("  All checks passed ✓")
    print('='*50)

    # Exit with error code if unhealthy (triggers GitHub notification)
    if issues:
        sys.exit(1)

if __name__ == "__main__":
    check()
