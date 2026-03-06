#!/usr/bin/env python3
"""
Cleanup script - Removes unnecessary files for GitHub release
"""

import os
import shutil

# Files to delete
FILES_TO_DELETE = [
    # Documentation (old/unnecessary)
    "2CAPTCHA_SETUP.md",
    "CLOUDFLARE_SOLUTIONS.md",
    "COOKIE_EXPIRATION_EXPLAINED.md",
    "COOKIE_GUIDE.md",
    "DEBUG_GUIDE.md",
    "DOCKER_GUIDE.md",
    "DOCKER_QUICKSTART.md",
    "PROXY_SOLUTION.md",
    "QUICKSTART.md",
    "SETUP_SCHEDULER.md",
    "SISTEM_NOU_INFO.md",
    "TELEGRAM_SETUP.md",
    "TROUBLESHOOTING.md",
    "WINDSCRIBE_DOCKER.md",
    
    # Docker files
    ".dockerignore",
    ".env.windscribe",
    "docker-compose.windscribe.yml",
    "docker-compose.yml",
    "docker-test.ps1",
    "docker-test.sh",
    "Dockerfile",
    "Dockerfile.windscribe",
    "save_cookies_docker.sh",
    "start.sh",
    "start_with_windscribe.sh",
    
    # Cookie files (user-specific)
    "cookies.json",
    "cookies_cont1.json",
    "cookies_cont2.json",
    "cookies_cont3.json",
    "cookies_cont4.json",
    
    # Test/debug scripts
    "analyze_wood_section.py",
    "extract_wood_sections.py",
    "measure_distance.py",
    "save_cookies.py",
    "test_cloudflare_methods.py",
    "test_telegram.py",
    "test_wood_detection_logic.py",
    
    # Old/unused scripts
    "main_playwright.py",
    "install_task.ps1",
    "quickstart.ps1",
    "run.bat",
    "run_scheduler.bat",
    "INSTALL_ADMIN.bat",
    
    # Debug HTML files
    "debug_cloudflare_page.html",
    "debug_cloudflare_page.png",
    "wood_analysis_results.json",
    "wood_section_debug.html",
    "wood_section_full.html",
    
    # Runtime files (will be recreated)
    "scheduler.lock",
    "last_opening.json",
    "schedule_config.json",
]

# Folders to delete
FOLDERS_TO_DELETE = [
    "debug_output",
    "downloaded_files",
    "__pycache__",
]

def main():
    print("\n" + "="*60)
    print("🧹 CLEANUP UNNECESSARY FILES")
    print("="*60 + "\n")
    
    deleted_files = 0
    deleted_folders = 0
    
    # Delete files
    print("📄 Deleting unnecessary files...\n")
    for file in FILES_TO_DELETE:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"   ✅ Deleted: {file}")
                deleted_files += 1
            except Exception as e:
                print(f"   ❌ Failed to delete {file}: {e}")
        else:
            print(f"   ⏭️  Skip (not found): {file}")
    
    # Delete folders
    print(f"\n📁 Deleting unnecessary folders...\n")
    for folder in FOLDERS_TO_DELETE:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                print(f"   ✅ Deleted folder: {folder}")
                deleted_folders += 1
            except Exception as e:
                print(f"   ❌ Failed to delete {folder}: {e}")
        else:
            print(f"   ⏭️  Skip (not found): {folder}")
    
    print("\n" + "="*60)
    print(f"✅ CLEANUP COMPLETE!")
    print(f"   📄 Deleted {deleted_files} files")
    print(f"   📁 Deleted {deleted_folders} folders")
    print("="*60 + "\n")
    
    print("📋 Remaining essential files:")
    essential = [
        "main.py",
        "scheduler.py",
        "setup.py",
        "install_task_new.ps1",
        "run_scheduler_hidden.vbs",
        "FIX_MULTIPLE_INSTANCES.bat",
        "REINSTALL_NO_CONSOLE.bat",
        "requirements.txt",
        "README.md",
        "config.example.json",
        ".gitignore",
        ".env.example"
    ]
    
    for file in essential:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ⚠️  Missing: {file}")
    
    print("\n💡 Run 'python setup.py' to configure the bot\n")

if __name__ == "__main__":
    main()
