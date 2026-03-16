"""
Profile Importer - Detects and imports existing browser profiles from the profiles folder.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from .profile_store import get_profile_root

logger = logging.getLogger(__name__)


class ProfileImporter:
    """Helper class to scan and import existing profiles from the managed profiles folder."""

    @staticmethod
    def get_profiles_folder() -> Optional[Path]:
        """Get the absolute path to profiles folder."""
        try:
            profiles_path = get_profile_root()
            if profiles_path.exists() and profiles_path.is_dir():
                return profiles_path
        except Exception as exc:
            logger.warning("Profiles folder is not available: %s", exc)
            return None

        logger.warning("Profiles folder not found")
        return None

    @staticmethod
    def scan_profiles() -> List[Dict[str, str]]:
        """
        Scan profiles folder and return list of discovered profiles.
        Returns: List of dicts with 'name' and 'path' keys.
        """
        profiles_folder = ProfileImporter.get_profiles_folder()
        if not profiles_folder:
            return []

        discovered = []
        try:
            for item in profiles_folder.iterdir():
                if not item.is_dir():
                    continue
                if item.name.startswith("_pending"):
                    continue
                discovered.append({"name": item.name, "path": str(item.resolve())})
            logger.info("Discovered %s profiles: %s", len(discovered), [p["name"] for p in discovered])
        except Exception as exc:
            logger.error("Error scanning profiles folder: %s", exc)

        return discovered

    @staticmethod
    def get_profile_metadata(profile_path: str) -> Optional[Dict]:
        """
        Extract metadata from a profile folder.
        Looks for profile_metadata.json or extracts from folder structure.
        """
        try:
            profile_dir = Path(profile_path)

            metadata_file = profile_dir / "profile_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    return metadata

            local_state_file = profile_dir / "Local State"
            if local_state_file.exists():
                try:
                    with open(local_state_file, "r", encoding="utf-8") as f:
                        json.load(f)
                        return {
                            "profile_folder": profile_dir.name,
                            "source": "chrome_profile",
                        }
                except Exception:
                    pass

            return {
                "profile_folder": profile_dir.name,
                "source": "folder_name",
            }
        except Exception as exc:
            logger.error("Error extracting metadata from %s: %s", profile_path, exc)
            return None

    @staticmethod
    def import_profiles(db: Session, account_crud_class) -> Dict[str, bool]:
        """
        Import all discovered profiles into database.
        Returns dict with profile names as keys and import success as values.
        """
        profiles = ProfileImporter.scan_profiles()
        results: Dict[str, bool] = {}

        if not profiles:
            logger.info("No profiles found to import")
            return results

        for profile in profiles:
            profile_name = profile["name"]
            profile_path = profile["path"]

            try:
                existing = account_crud_class.get_by_name(db, profile_name)
                if existing:
                    logger.info("Account '%s' already exists, skipping...", profile_name)
                    results[profile_name] = False
                    continue

                metadata = ProfileImporter.get_profile_metadata(profile_path)
                if not metadata:
                    logger.warning("Could not extract metadata for %s", profile_name)
                    results[profile_name] = False
                    continue

                account = account_crud_class.create(
                    db,
                    account_name=profile_name,
                    steam_username=profile_name,
                )

                account.browser_profile_path = profile_path
                db.commit()
                db.refresh(account)

                logger.info("Successfully imported profile: %s", profile_name)
                results[profile_name] = True

            except Exception as exc:
                logger.error("Error importing profile %s: %s", profile_name, exc)
                results[profile_name] = False

        return results

    @staticmethod
    def import_single_profile(db: Session, profile_name: str, account_crud_class) -> bool:
        """Import a single profile by name."""
        profiles = ProfileImporter.scan_profiles()
        profile_data = next((p for p in profiles if p["name"] == profile_name), None)

        if not profile_data:
            logger.error("Profile '%s' not found", profile_name)
            return False

        try:
            existing = account_crud_class.get_by_name(db, profile_name)
            if existing:
                logger.warning("Profile '%s' already imported", profile_name)
                return False

            account = account_crud_class.create(
                db,
                account_name=profile_name,
                steam_username=profile_name,
            )

            account.browser_profile_path = profile_data["path"]
            db.commit()
            db.refresh(account)

            logger.info("Successfully imported single profile: %s", profile_name)
            return True

        except Exception as exc:
            logger.error("Error importing profile %s: %s", profile_name, exc)
            db.rollback()
            return False
