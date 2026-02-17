"""
Load data from Hugging Face Datasets.
This module downloads data from HF Datasets and caches it locally.
"""

import os
import gzip
import shutil
import tempfile
from typing import Optional
import streamlit as st

try:
    from huggingface_hub import hf_hub_download, list_repo_files
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

# Hugging Face Dataset repository
HF_DATASET_REPO = "bugtap/dplus-data"
HF_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'hf_cache')


def download_from_hf(progress_callback=None) -> int:
    """
    Download data files from Hugging Face Datasets.

    Returns:
        Number of files downloaded
    """
    if not HF_HUB_AVAILABLE:
        print("[HF] huggingface_hub not available, skipping HF download")
        return 0

    os.makedirs(HF_CACHE_DIR, exist_ok=True)

    try:
        # List files in the dataset
        files = list_repo_files(HF_DATASET_REPO, repo_type="dataset")

        # Filter for data files
        data_files = [f for f in files if f.endswith(('.csv.gz', '.xlsx', '.csv'))]

        if not data_files:
            print("[HF] No data files found in dataset")
            return 0

        downloaded = 0
        total = len(data_files)

        for i, filename in enumerate(data_files):
            if progress_callback:
                progress_callback(i / total, f"Downloading: {filename}")

            try:
                local_path = hf_hub_download(
                    repo_id=HF_DATASET_REPO,
                    filename=filename,
                    repo_type="dataset",
                    cache_dir=HF_CACHE_DIR
                )

                # Copy to data folder for database to find
                dest_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
                os.makedirs(dest_folder, exist_ok=True)
                dest_path = os.path.join(dest_folder, os.path.basename(filename))

                if not os.path.exists(dest_path):
                    shutil.copy2(local_path, dest_path)

                downloaded += 1
                print(f"[HF] Downloaded: {filename}")

            except Exception as e:
                print(f"[HF] Error downloading {filename}: {e}")

        return downloaded

    except Exception as e:
        print(f"[HF] Error accessing dataset: {e}")
        return 0


@st.cache_resource
def ensure_data_available() -> bool:
    """
    Ensure data is available, downloading from HF if needed.

    Returns:
        True if data is available
    """
    # Check if data folder has files
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')

    if os.path.exists(data_dir):
        files = [f for f in os.listdir(data_dir) if f.endswith(('.csv.gz', '.xlsx', '.csv'))]
        if len(files) > 0:
            return True

    # Try to download from HF
    if HF_HUB_AVAILABLE:
        print("[HF] No local data found, downloading from Hugging Face...")
        downloaded = download_from_hf()
        return downloaded > 0

    return False
