import hashlib
import logging
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, base_path: str = "./storage/attachments"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, message_id: str, file_id: UUID, filename: str) -> Path:
        """Generate storage path: storage/attachments/{message_id}/{file_id}_{filename}"""
        message_dir = self.base_path / str(message_id)
        message_dir.mkdir(parents=True, exist_ok=True)
        return message_dir / f"{file_id}_{filename}"

    async def save_file(
        self, file: UploadFile, message_id: UUID, file_id: UUID
    ) -> tuple[str, int, str]:
        """
        Save uploaded file to disk
        Returns: (storage_url, size_bytes, checksum)
        """
        try:
            content = await file.read()
            size_bytes = len(content)

            # Calculate checksum
            checksum = hashlib.sha256(content).hexdigest()

            file_path = self._get_file_path(message_id, file_id, file.filename)
            with open(file_path, "wb") as f:
                f.write(content)
            # Generate storage URL (relative path)
            storage_url = str(file_path.relative_to(self.base_path.parent))

            return storage_url, size_bytes, checksum

        except Exception as e:
            logger.error(f"File save error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File save error: {str(e)}",
            )

    def delete_file(self, storage_url: str) -> None:
        """Delete file from disk given its storage URL"""
        try:
            file_path = Path(storage_url)
            if file_path.exists():
                file_path.unlink()

                # Remove empty parent directory if exists
                parent_dir = file_path.parent
                if parent_dir.exists() and not any(parent_dir.iterdir()):
                    parent_dir.rmdir()
        except Exception as e:
            logger.warning(f"Failed to delete file {storage_url}: {str(e)}")


storage_service = StorageService()
