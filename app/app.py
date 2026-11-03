import boto3
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .config import Config

bp = Blueprint("main", __name__)

# Health check endpoint
@bp.route("/health")
def health():
    return {"status": "ok"}, 200

# Create a single shared s3 client using config values
s3 = boto3.client(
    "s3",
    endpoint_url=Config.S3_ENDPOINT_URL,
    aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    region_name=Config.S3_REGION,
    use_ssl=Config.S3_USE_SSL,
)

# Ensure the default bucket exists on first import (only when using a local mock)
try:
    s3.head_bucket(Bucket=Config.S3_BUCKET_NAME)
except Exception:
    # If bucket does not exist, create it (moto allows creation)
    try:
        s3.create_bucket(Bucket=Config.S3_BUCKET_NAME)
    except Exception:
        pass


@bp.route("/")
def index():
    """List objects in the default bucket."""
    try:
        resp = s3.list_objects_v2(Bucket=Config.S3_BUCKET_NAME)
        objects = resp.get("Contents", [])
        return render_template(
            "index.html",
            objects=objects,
            bucket=Config.S3_BUCKET_NAME,
        )
    except Exception as e:
        flash(f"Error listing objects: {str(e)}", "error")
        return render_template("index.html", objects=[], bucket=Config.S3_BUCKET_NAME)


@bp.route("/bucket/<bucket_name>")
def bucket_index(bucket_name):
    """List objects in a specific bucket."""
    try:
        resp = s3.list_objects_v2(Bucket=bucket_name)
        objects = resp.get("Contents", [])
        return render_template("bucket_index.html", objects=objects, bucket=bucket_name)
    except Exception as e:
        flash(f"Error listing objects: {str(e)}", "error")
        return render_template("bucket_index.html", objects=[], bucket=bucket_name)


@bp.route("/bucket/<bucket_name>/upload", methods=["GET", "POST"])
def upload_file(bucket_name):
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("No file selected", "error")
            return redirect(request.url)
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        try:
            s3.upload_fileobj(file, bucket_name, filename)
            flash(f"Uploaded {filename} successfully", "success")
        except Exception as e:
            flash(f"Upload error: {str(e)}", "error")
        return redirect(url_for("main.bucket_index", bucket_name=bucket_name))
    return render_template("upload.html", bucket_name=bucket_name)


@bp.route("/bucket/<bucket_name>/download/<path:filename>")
def download_file(bucket_name, filename):
    """Return a presigned URL for download (valid 1 hour)."""
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": filename},
            ExpiresIn=3600,
        )
        return jsonify({"download_url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/bucket/<bucket_name>/delete/<path:filename>", methods=["POST"])
def delete_file(bucket_name, filename):
    try:
        s3.delete_object(Bucket=bucket_name, Key=filename)
        flash("Object deleted", "success")
    except Exception as e:
        flash(f"Delete error: {str(e)}", "error")
    return redirect(url_for("main.bucket_index", bucket_name=bucket_name))