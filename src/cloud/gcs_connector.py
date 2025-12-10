"""
GCS (Google Cloud Storage) Connector

Handles file operations with Google Cloud Storage buckets
"""

from google.cloud import storage
from google.cloud.exceptions import NotFound
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
from datetime import datetime
import os

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class GCSConnector:
    """
    Google Cloud Storage connector for cloud storage operations
    
    Supports:
    - GCP Cloud Storage buckets
    - Upload/download files and data
    - List and delete operations
    - Metadata support
    """
    
    def __init__(
        self,
        bucket_name: str,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None
    ):
        """
        Initialize GCS connector
        
        Args:
            bucket_name: GCS bucket name
            project_id: GCP project ID (optional if set in credentials)
            credentials_path: Path to service account JSON key file
                            (if None, uses GOOGLE_APPLICATION_CREDENTIALS env var)
        """
        self.bucket_name = bucket_name
        self.project_id = project_id
        
        # Set credentials if provided
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            logger.info(f"Using credentials from: {credentials_path}")
        
        # Create GCS client
        if project_id:
            self.client = storage.Client(project=project_id)
        else:
            self.client = storage.Client()
        
        logger.info(f"GCSConnector initialized for bucket: {bucket_name}")
        
        # Get or create bucket
        self.bucket = self._get_or_create_bucket()
    
    def _get_or_create_bucket(self):
        """Get bucket or create if doesn't exist"""
        try:
            bucket = self.client.get_bucket(self.bucket_name)
            logger.info(f"Bucket '{self.bucket_name}' exists")
            return bucket
        except NotFound:
            logger.info(f"Bucket '{self.bucket_name}' not found, creating...")
            bucket = self.client.create_bucket(self.bucket_name)
            logger.info(f"Bucket '{self.bucket_name}' created")
            return bucket
    
    def upload_file(
        self,
        local_path: Path,
        gcs_path: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Upload a file to GCS
        
        Args:
            local_path: Path to local file
            gcs_path: GCS object path (blob name)
            metadata: Optional metadata dict
        
        Returns:
            True if successful
        """
        try:
            blob = self.bucket.blob(gcs_path)
            
            # Set metadata if provided
            if metadata:
                blob.metadata = metadata
            
            blob.upload_from_filename(str(local_path))
            logger.info(f"Uploaded: {local_path.name} -> gs://{self.bucket_name}/{gcs_path}")
            return True
        
        except FileNotFoundError:
            logger.error(f"File not found: {local_path}")
            return False
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False
    
    def upload_data(
        self,
        data: Any,
        gcs_path: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Upload data (dict, list, string) directly to GCS
        
        Args:
            data: Data to upload (will be JSON serialized if dict/list)
            gcs_path: GCS object path
            metadata: Optional metadata
        
        Returns:
            True if successful
        """
        try:
            blob = self.bucket.blob(gcs_path)
            
            # Set metadata if provided
            if metadata:
                blob.metadata = metadata
            
            # Convert data to string
            if isinstance(data, (dict, list)):
                content = json.dumps(data, indent=2)
                content_type = 'application/json'
            elif isinstance(data, str):
                content = data
                content_type = 'text/plain'
            else:
                content = str(data)
                content_type = 'application/octet-stream'
            
            blob.upload_from_string(content, content_type=content_type)
            logger.info(f"Uploaded data -> gs://{self.bucket_name}/{gcs_path}")
            return True
        
        except Exception as e:
            logger.error(f"Data upload failed: {e}")
            return False
    
    def download_file(self, gcs_path: str, local_path: Path) -> bool:
        """
        Download a file from GCS
        
        Args:
            gcs_path: GCS object path
            local_path: Local path to save file
        
        Returns:
            True if successful
        """
        try:
            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            blob = self.bucket.blob(gcs_path)
            blob.download_to_filename(str(local_path))
            
            logger.info(f"Downloaded: gs://{self.bucket_name}/{gcs_path} -> {local_path}")
            return True
        
        except NotFound:
            logger.error(f"Object not found: {gcs_path}")
            return False
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    
    def download_data(self, gcs_path: str) -> Optional[Any]:
        """
        Download data from GCS and parse if JSON
        
        Args:
            gcs_path: GCS object path
        
        Returns:
            Parsed data (dict/list if JSON, string otherwise)
        """
        try:
            blob = self.bucket.blob(gcs_path)
            content = blob.download_as_text()
            
            # Try to parse as JSON
            if gcs_path.endswith('.json') or blob.content_type == 'application/json':
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content
            else:
                return content
        
        except NotFound:
            logger.error(f"Object not found: {gcs_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to download data: {e}")
            return None
    
    def list_files(self, prefix: str = '', max_results: int = 1000) -> List[Dict[str, Any]]:
        """
        List files in bucket with given prefix
        
        Args:
            prefix: Path prefix to filter
            max_results: Maximum number of results
        
        Returns:
            List of file info dicts
        """
        try:
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=prefix,
                max_results=max_results
            )
            
            files = []
            for blob in blobs:
                files.append({
                    'name': blob.name,
                    'size': blob.size,
                    'updated': blob.updated,
                    'content_type': blob.content_type,
                    'metadata': blob.metadata
                })
            
            logger.info(f"Listed {len(files)} files with prefix '{prefix}'")
            return files
        
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def delete_file(self, gcs_path: str) -> bool:
        """
        Delete a file from GCS
        
        Args:
            gcs_path: GCS object path
        
        Returns:
            True if successful
        """
        try:
            blob = self.bucket.blob(gcs_path)
            blob.delete()
            logger.info(f"Deleted: gs://{self.bucket_name}/{gcs_path}")
            return True
        
        except NotFound:
            logger.warning(f"Object not found (already deleted?): {gcs_path}")
            return True  # Already deleted, consider success
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
    
    def file_exists(self, gcs_path: str) -> bool:
        """
        Check if file exists in GCS
        
        Args:
            gcs_path: GCS object path
        
        Returns:
            True if exists
        """
        blob = self.bucket.blob(gcs_path)
        return blob.exists()
    
    def get_file_metadata(self, gcs_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata
        
        Args:
            gcs_path: GCS object path
        
        Returns:
            Metadata dict or None
        """
        try:
            blob = self.bucket.blob(gcs_path)
            blob.reload()  # Fetch latest metadata
            
            return {
                'name': blob.name,
                'size': blob.size,
                'content_type': blob.content_type,
                'updated': blob.updated,
                'created': blob.time_created,
                'metadata': blob.metadata
            }
        except NotFound:
            logger.error(f"Object not found: {gcs_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return None


if __name__ == "__main__":
    # Example usage
    print("Testing GCSConnector...")
    
    # NOTE: Requires GCP credentials
    # Set GOOGLE_APPLICATION_CREDENTIALS environment variable or pass credentials_path
    
    # connector = GCSConnector(
    #     bucket_name='your-bucket-name',
    #     project_id='your-project-id',
    #     credentials_path='/path/to/service-account-key.json'
    # )
    
    # # Upload data
    # data = {"test": "data"}
    # connector.upload_data(data, 'test/data.json')
    
    # # Download
    # downloaded = connector.download_data('test/data.json')
    # print(f"Downloaded: {downloaded}")
    
    # # List files
    # files = connector.list_files(prefix='test/')
    # print(f"Found {len(files)} files")
    
    print("✅ GCSConnector ready (configure with actual credentials to test)")
