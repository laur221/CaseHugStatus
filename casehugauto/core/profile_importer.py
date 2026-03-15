"""
Profile Importer - Detects and imports existing browser profiles from the profiles/ folder
"""
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ProfileImporter:
    """Helper class to scan and import existing profiles from profiles/ folder"""
    
    PROFILES_FOLDER = "profiles"
    
    @staticmethod
    def get_profiles_folder() -> Optional[Path]:
        """Get the absolute path to profiles folder"""
        # Look for profiles folder relative to workspace root
        current_dir = Path.cwd()
        profiles_path = current_dir / ProfileImporter.PROFILES_FOLDER
        
        if profiles_path.exists() and profiles_path.is_dir():
            return profiles_path
        
        logger.warning(f"Profiles folder not found at {profiles_path}")
        return None
    
    @staticmethod
    def scan_profiles() -> List[Dict[str, str]]:
        """
        Scan profiles folder and return list of discovered profiles
        Returns: List of dicts with 'name' and 'path' keys
        """
        profiles_folder = ProfileImporter.get_profiles_folder()
        if not profiles_folder:
            return []
        
        discovered = []
        try:
            for item in profiles_folder.iterdir():
                if item.is_dir():
                    discovered.append({
                        'name': item.name,
                        'path': str(item)
                    })
            logger.info(f"Discovered {len(discovered)} profiles: {[p['name'] for p in discovered]}")
        except Exception as e:
            logger.error(f"Error scanning profiles folder: {e}")
        
        return discovered
    
    @staticmethod
    def get_profile_metadata(profile_path: str) -> Optional[Dict]:
        """
        Extract metadata from a profile folder
        Looks for profile_metadata.json or extracts from folder structure
        """
        try:
            profile_dir = Path(profile_path)
            
            # Check for metadata file
            metadata_file = profile_dir / "profile_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    return metadata
            
            # Try to extract Steam ID from Local State file (Chrome profile)
            local_state_file = profile_dir / "Local State"
            if local_state_file.exists():
                try:
                    with open(local_state_file, 'r', encoding='utf-8') as f:
                        local_state = json.load(f)
                        # Minimal metadata extracted
                        return {
                            'profile_folder': profile_dir.name,
                            'source': 'chrome_profile'
                        }
                except:
                    pass
            
            # Default: use folder name as identifier
            return {
                'profile_folder': profile_dir.name,
                'source': 'folder_name'
            }
        except Exception as e:
            logger.error(f"Error extracting metadata from {profile_path}: {e}")
            return None
    
    @staticmethod
    def import_profiles(db: Session, account_crud_class) -> Dict[str, bool]:
        """
        Import all discovered profiles into database
        Returns dict with profile names as keys and import success as values
        """
        profiles = ProfileImporter.scan_profiles()
        results = {}
        
        if not profiles:
            logger.info("No profiles found to import")
            return results
        
        for profile in profiles:
            profile_name = profile['name']
            profile_path = profile['path']
            
            try:
                # Check if account already exists
                existing = account_crud_class.get_by_name(db, profile_name)
                if existing:
                    logger.info(f"Account '{profile_name}' already exists, skipping...")
                    results[profile_name] = False
                    continue
                
                # Extract metadata
                metadata = ProfileImporter.get_profile_metadata(profile_path)
                if not metadata:
                    logger.warning(f"Could not extract metadata for {profile_name}")
                    results[profile_name] = False
                    continue
                
                # Create new account
                account = account_crud_class.create(
                    db,
                    account_name=profile_name,
                    steam_username=profile_name
                )
                
                # Update browser profile path to point to the existing profile
                account.browser_profile_path = profile_path
                db.commit()
                db.refresh(account)
                
                logger.info(f"Successfully imported profile: {profile_name}")
                results[profile_name] = True
                
            except Exception as e:
                logger.error(f"Error importing profile {profile_name}: {e}")
                results[profile_name] = False
        
        return results
    
    @staticmethod
    def import_single_profile(db: Session, profile_name: str, account_crud_class) -> bool:
        """
        Import a single profile by name
        """
        profiles = ProfileImporter.scan_profiles()
        profile_data = next((p for p in profiles if p['name'] == profile_name), None)
        
        if not profile_data:
            logger.error(f"Profile '{profile_name}' not found")
            return False
        
        try:
            # Check if already imported
            existing = account_crud_class.get_by_name(db, profile_name)
            if existing:
                logger.warning(f"Profile '{profile_name}' already imported")
                return False
            
            # Create account
            account = account_crud_class.create(
                db,
                account_name=profile_name,
                steam_username=profile_name
            )
            
            # Set to existing profile path
            account.browser_profile_path = profile_data['path']
            db.commit()
            db.refresh(account)
            
            logger.info(f"Successfully imported single profile: {profile_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error importing profile {profile_name}: {e}")
            db.rollback()
            return False
