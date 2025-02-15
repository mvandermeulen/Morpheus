import io
import logging
import uuid
from typing import Union

import boto3
from PIL import Image
from fastapi import UploadFile
from rich import print

from morpheus_data.config import get_settings
from morpheus_data.repository.files.files_interface import FileRepositoryInterface
from morpheus_data.utils.images import from_image_to_bytes
from morpheus_data.utils.timer import get_timestamp

settings = get_settings()
logger = logging.getLogger(__name__)

AWS_ACCESS_KEY_ID = settings.aws_access_key_id
AWS_SECRET_ACCESS_KEY = settings.aws_secret_access_key
IMAGES_BUCKET = settings.images_bucket


class S3ImagesRepository(FileRepositoryInterface):
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )

    def upload_file(self, *, file: UploadFile, folder_name: str):
        try:
            contents = file.file.read()
            temp_file = io.BytesIO()
            temp_file.write(contents)
            temp_file.seek(0)
            file_name = get_file_name(file=file, folder_name=folder_name)
            self.s3.upload_fileobj(temp_file, IMAGES_BUCKET, file_name)
            temp_file.close()
            return file_name
        except Exception as e:
            logger.error("Error uploading the file to AWS S3")
            logger.error(e)

    def upload_image(self, image: Image.Image, folder_name: str):
        try:
            img_bytes = from_image_to_bytes(image)
            file_name = get_file_name(file=image, folder_name=folder_name)
            with io.BytesIO(img_bytes) as fstream:
                fstream.name = file_name
                self.s3.upload_fileobj(
                    fstream,
                    IMAGES_BUCKET,
                    file_name,
                    ExtraArgs={"ContentType": "image/png"},
                )
            return file_name
        except Exception as e:
            logger.error(e)
            logger.error("Error uploading the file to AWS S3")

    def move_file(self, *, source: str, target: str):
        try:
            source_folder, source_name = get_file_path(object_url=source)
            src_key = f"{source_folder}/{source_name}"
            dst_key = f"{target}/{source_name}"

            self.s3.copy_object(
                Bucket=IMAGES_BUCKET,
                CopySource={"Bucket": IMAGES_BUCKET, "Key": src_key},
                Key=dst_key,
            )

            return dst_key
        except Exception as e:
            logger.error("Error moving the image to a folder")
            logger.error(e)

    def get_file(self, filepath: str):
        result = self.s3.list_objects_v2(Bucket=IMAGES_BUCKET, Prefix=filepath)
        return [item["Key"] for item in result.get("Contents", [])]

    def get_files(self, folder_name: str = settings.images_temp_bucket, max_keys: int | None = None):
        try:
            params = {"Bucket": IMAGES_BUCKET, "Prefix": folder_name}
            if max_keys:
                params.update(MaxKeys=max_keys)

            response = self.s3.list_objects_v2(**params)
            images = []
            for content in response.get("Contents", []):
                key = content.get("Key")
                if key is not None and isinstance(key, str):
                    images.append(self.generate_public_url(file_name=key))
            return images
        except Exception as e:
            logger.error("Error getting the images from AWS S3")
            logger.error(e)

    @staticmethod
    def generate_public_url(*, file_name: str):
        try:
            return f"https://{IMAGES_BUCKET}.s3.amazonaws.com/{file_name}"
        except Exception as e:
            logger.error("Error generating the public url")
            logger.error(e)

    def get_file_url(self, *, filename: str):
        try:
            image_url = ""
            response = self.s3.list_objects_v2(Bucket=IMAGES_BUCKET, Prefix=filename)
            for content in response.get("Contents", []):
                key = content.get("Key")
                image_url = self.generate_public_url(file_name=key)
            return image_url
        except Exception as e:
            print(e)

    def get_file_urls(self, filenames: list[str]):
        image_urls = []
        for filename in filenames:
            image_url = self.get_file_url(filename=filename)
            image_urls.append(image_url)
        return image_urls

    def get_content(self, folder: str = "") -> list:
        if not folder:
            result = self.s3.list_objects_v2(Bucket=IMAGES_BUCKET, Delimiter="/")
            return [prefix["Prefix"] for prefix in result.get("CommonPrefixes", [])]
        else:
            result = self.s3.list_objects_v2(Bucket=IMAGES_BUCKET, Prefix=folder)
            return [item["Key"] for item in result.get("Contents", [])]

    def delete_file(self, filepath: str):
        try:
            file_to_delete = [{"Key": filepath}]
            self.s3.delete_objects(Bucket=IMAGES_BUCKET, Delete={"Objects": file_to_delete})
        except Exception as e:
            logger.error("Error deleting the files from AWS S3")
            logger.error(e)
            return False
        return True

    def delete_files(self, folder_name: str):
        content = self.get_content(folder_name)
        if content:
            try:
                files_to_delete = [{"Key": file} for file in content]
                print("Files to delete:", files_to_delete)
                self.s3.delete_objects(Bucket=IMAGES_BUCKET, Delete={"Objects": files_to_delete})
            except Exception as e:
                logger.error("Error deleting the files from AWS S3")
                logger.error(e)
                return False
        return True


def get_file_name(*, file: Union[UploadFile, Image.Image], folder_name: str):
    file_name = getattr(file, "filename", None)
    if not file_name:
        file_name = f"{uuid.uuid4()}-{get_timestamp()}.png"

    return f"{folder_name}/{file_name}"


def get_file_path(*, object_url: str):
    splits = object_url.split("/")
    folder, filename = splits[-2], splits[-1]
    return folder, filename
