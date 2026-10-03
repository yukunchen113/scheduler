"""
Plex One-Stop Setup Wizard

A unified setup command for Plex:
- Scaffolds workspace: routines/, daily/, weekly/
- Seeds starter routines: daily.txt, school.txt
- Stores preferences and secrets into ~/.config/plex/config.json (0600 permissions)
- Guides Google Calendar OAuth setup & Notion API integration
- Links / installs the VS Code extension
"""

import argparse
import getpass
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional

from plex.config import get_config_dir, get_config_file, load_config, save_config

DEFAULT_DAILY_ROUTINE = """morning:
wake up [20]
washroom [20]
skincare [10]
get ready [10]

night:
cleanup/wash dishes [15]
schedule [25]
get ready for bed [20]
"""

DEFAULT_SCHOOL_ROUTINE = """mon:
lecture [1h30] (10am)
lab [2h] (14:00)

tue:
lecture [1h30] (11:30am)

wed:
lecture [1h30] (10am)
tutorial [1h] (16:00)

thu:
lecture [1h30] (11:30am)

fri:
lecture [1h30] (10am)
"""


def scaffold_workspace(target_dir: str = ".") -> None:
    """Scaffolds routines/, daily/, weekly/ directories with starter templates."""
    base = Path(target_dir).resolve()
    routines_dir = base / "routines"
    daily_dir = base / "daily"
    weekly_dir = base / "weekly"

    routines_dir.mkdir(parents=True, exist_ok=True)
    daily_dir.mkdir(parents=True, exist_ok=True)
    weekly_dir.mkdir(parents=True, exist_ok=True)

    daily_txt = routines_dir / "daily.txt"
    if not daily_txt.exists():
        daily_txt.write_text(DEFAULT_DAILY_ROUTINE)
        print(f"  ✓ Created starter routine: routines/daily.txt")

    school_txt = routines_dir / "school.txt"
    if not school_txt.exists():
        school_txt.write_text(DEFAULT_SCHOOL_ROUTINE)
        print(f"  ✓ Created starter routine: routines/school.txt")

    print(f"  ✓ Workspace directories verified in {base}")


def build_vsix(output_path: Optional[str] = None) -> Path:
    """Builds a portable .vsix extension package without requiring node or vsce."""
    repo_root = Path(__file__).resolve().parent.parent
    extension_source = repo_root / "plex-vscode"
    pkg_file = extension_source / "package.json"
    version = "0.1.1"
    if pkg_file.exists():
        try:
            with open(pkg_file) as f:
                version = json.load(f).get("version", "0.1.1")
        except Exception:
            pass
    if output_path is None:
        output_path = f"plex-vscode-{version}.vsix"
    out_file = Path(output_path).resolve()

    content_types = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="vsixmanifest" ContentType="text/xml"/>
  <Default Extension="json" ContentType="application/json"/>
  <Default Extension="js" ContentType="application/javascript"/>
  <Default Extension="md" ContentType="text/markdown"/>
  <Default Extension="html" ContentType="text/html"/>
</Types>"""

    vsix_manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Id="plex-vscode" Version="{version}" Language="en-US" Publisher="plex"/>
    <DisplayName>Plex Time-Blocking Scheduler</DisplayName>
    <Description xml:space="preserve">Native VS Code CodeLens, auto-evaluation, and one-click actions for Plex planner</Description>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>
  </Assets>
</PackageManifest>"""

    with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("extension.vsixmanifest", vsix_manifest)
        z.write(extension_source / "package.json", "extension/package.json")
        z.write(extension_source / "extension.js", "extension/extension.js")
        if (extension_source / "README.md").exists():
            z.write(extension_source / "README.md", "extension/README.md")
        media_dir = extension_source / "media"
        if media_dir.exists():
            for m_file in media_dir.glob("*"):
                if m_file.is_file():
                    z.write(m_file, f"extension/media/{m_file.name}")

    return out_file


def setup_vscode_extension() -> bool:
    """Builds and installs the VS Code extension."""
    repo_root = Path(__file__).resolve().parent.parent
    extension_source = repo_root / "plex-vscode"
    if not extension_source.exists():
        return False

    vsix_file = build_vsix()
    print(f"  ✓ Built portable extension package: {vsix_file.name}")

    if shutil.which("code"):
        try:
            res = subprocess.run(
                ["code", "--install-extension", str(vsix_file), "--force"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                print(
                    f"  ✓ Installed extension in VS Code via 'code --install-extension'"
                )
                return True
        except Exception:
            pass

    # Fallback to linking ~/.vscode/extensions/plex-vscode
    vscode_ext_dir = Path.home() / ".vscode" / "extensions"
    if vscode_ext_dir.exists():
        target_link = vscode_ext_dir / "plex-vscode"
        if not target_link.exists():
            try:
                os.symlink(extension_source, target_link)
                print(f"  ✓ Linked extension to ~/.vscode/extensions/plex-vscode")
                return True
            except Exception:
                pass
        else:
            return True
    return True


def run_setup(
    target_dir: str = ".",
    non_interactive: bool = False,
    email: Optional[str] = None,
    credentials_file: Optional[str] = None,
    notion_api_key: Optional[str] = None,
    skip_auth: bool = False,
) -> None:
    """One-stop setup command for Plex."""
    print("=" * 60)
    print("               PLEX ONE-STOP SETUP WIZARD")
    print("=" * 60)

    # 1. Workspace Scaffolding
    print("\n[1/4] Scaffolding workspace...")
    scaffold_workspace(target_dir)

    # 2. Config & Secrets
    print("\n[2/4] Configuring settings and secrets...")
    config = load_config()
    config_dir = get_config_dir()

    # Email
    if email:
        config["calendar"]["email"] = email
    elif not non_interactive:
        current_email = config["calendar"].get("email", "primary")
        user_email = input(f"  Google Calendar ID/Email [{current_email}]: ").strip()
        if user_email:
            config["calendar"]["email"] = user_email

    # Google Calendar
    if not skip_auth:
        want_google = False
        if credentials_file:
            want_google = True
        elif not non_interactive:
            choice = (
                input("  Enable Google Calendar & Tasks sync? (y/N): ").strip().lower()
            )
            want_google = choice in ["y", "yes"]

        if want_google:
            creds_path = credentials_file
            if not creds_path and not non_interactive:
                default_cand = "credentials.json"
                if not os.path.exists(default_cand):
                    default_cand = str(config_dir / "credentials.json")
                prompt_str = f"  Path to credentials.json [{default_cand}]: "
                creds_input = input(prompt_str).strip()
                creds_path = creds_input if creds_input else default_cand

            if creds_path and os.path.exists(creds_path):
                dest_creds = config_dir / "credentials.json"
                if Path(creds_path).resolve() != dest_creds.resolve():
                    shutil.copyfile(creds_path, dest_creds)
                config["calendar"]["credentials_file"] = str(dest_creds)
                config["calendar"]["enabled"] = True
                print(f"  ✓ Saved credentials to {dest_creds}")

                # Run OAuth browser flow
                try:
                    from plex.authenticate import authenticate

                    print("  Launching Google OAuth browser authorization...")
                    authenticate(str(dest_creds))
                    print("  ✓ Google authentication complete!")
                except Exception as err:
                    print(f"  ! Google authentication failed: {err}")
                    print("    You can retry anytime by running: plex --authenticate")
            else:
                print(f"  ! Credentials file not found. Skipping Google OAuth for now.")
                print("    You can add it later via: plex setup")

    # Notion
    if notion_api_key:
        config["notion"]["api_key"] = notion_api_key
        config["notion"]["enabled"] = True
    elif not non_interactive:
        want_notion = input("  Enable Notion sync? (y/N): ").strip().lower() in [
            "y",
            "yes",
        ]
        if want_notion:
            key = getpass.getpass("  Enter Notion API key (hidden): ").strip()
            if key:
                config["notion"]["api_key"] = key
                config["notion"]["enabled"] = True
                print("  ✓ Notion API key configured!")

    cfg_file = save_config(config)
    print(f"  ✓ Stored configuration and secrets in {cfg_file} (mode 0600)")

    # 3. VS Code Extension
    print("\n[3/4] Checking VS Code integration...")
    ext_installed = setup_vscode_extension()
    if shutil.which("code"):
        print("  ✓ VS Code CLI ('code') detected")
    else:
        print(
            "  ! 'code' command not found in PATH (VS Code GUI can still load extensions)"
        )

    # 4. Initialize current week sample
    print("\n[4/4] Initializing weekly plan...")
    try:
        from plex.weekly import init_weekly_file

        weekly_file = init_weekly_file(expand=True)
        print(f"  ✓ Initialized current week: {weekly_file}")
    except Exception as err:
        print(f"  ! Week initialization notice: {err}")

    print("\n" + "=" * 60)
    print("                 SETUP COMPLETE! 🎉")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Open this workspace in VS Code:")
    print("     code .")
    print("  2. In VS Code, press Cmd+Shift+P -> 'Developer: Reload Window'")
    print(
        "  3. Open any weekly file in weekly/ or press Cmd+Shift+P -> 'Plex: Generate Weekly Plan...'"
    )
    print("  4. Edit your schedule with Alt+Up / Alt+Down and save with Cmd+S!\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plex One-Stop Setup Wizard")
    parser.add_argument(
        "--default",
        action="store_true",
        help="Run with sensible defaults (non-interactive, local offline mode)",
    )
    parser.add_argument(
        "--non-interactive", action="store_true", help="Do not prompt for inputs"
    )
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Google Calendar ID/email (defaults to 'primary')",
    )
    parser.add_argument(
        "--credentials", type=str, default=None, help="Path to Google credentials.json"
    )
    parser.add_argument("--notion-key", type=str, default=None, help="Notion API key")
    parser.add_argument(
        "--skip-auth", action="store_true", help="Skip Google Calendar OAuth flow"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=".",
        help="Target workspace directory (default: current directory)",
    )

    args = parser.parse_args()

    non_int = args.default or args.non_interactive
    skip_auth = args.skip_auth or args.default

    run_setup(
        target_dir=args.dir,
        non_interactive=non_int,
        email=args.email,
        credentials_file=args.credentials,
        notion_api_key=args.notion_key,
        skip_auth=skip_auth,
    )


if __name__ == "__main__":
    main()
