from pathlib import Path

BASE = Path(".")
OUT_DIR = BASE / "extracted_txt"
OUT_DIR.mkdir(exist_ok=True)

files = [
    "nginx/html/web_dashboard.html",
    "nginx/html/js/wed_dashboard/dashboard_api.js",
    "nginx/html/js/wed_dashboard/dashboard_app.js",
    "nginx/html/css/wed_dashboard/dashboard_style.css",
    "server_api/src/modules/dashboard/router.py",
    "server_api/src/modules/dashboard/service.py",
    "server_api/src/main.py",
    "server_api/src/api/v1/router.py",
    "nginx/html/css/ui.css",
    "nginx/html/css/style.css",
]

output_path = OUT_DIR / "for_claude_kpi_card.txt"

with open(output_path, "w", encoding="utf-8", newline="\n") as out:
    for file in files:
        p = BASE / file
        out.write("=" * 100 + "\n")
        out.write(f"FILE: {file}\n")
        out.write("=" * 100 + "\n\n")

        if p.exists():
            try:
                content = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = p.read_text(encoding="utf-8-sig")
            out.write(content)
            out.write("\n\n")
        else:
            out.write(f"[MISSING] {file}\n\n")

print(f"완료: {output_path}")