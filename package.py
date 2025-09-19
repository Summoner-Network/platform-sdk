import sys
import os
import tarfile
import gzip
import time

def compress_folder_gzip(folder_path: str):
    """
    Archives a folder into a .tar.gz file using the built-in gzip library.

    Args:
        folder_path (str): The relative path to the folder to compress.
    """
    # 1. Validate the input path
    abs_folder_path = os.path.abspath(folder_path)
    if not os.path.isdir(abs_folder_path):
        print(f"Error: The path '{folder_path}' is not a valid directory.")
        sys.exit(1)

    # 2. Determine the output filename
    folder_name = os.path.basename(abs_folder_path)
    output_filename = f"{folder_name}.tar.gz"

    if os.path.exists(output_filename):
        print(f"Error: Output file '{output_filename}' already exists. Please remove it first.")
        sys.exit(1)
        
    print(f"Starting compression of '{folder_name}' into '{output_filename}'...")
    start_time = time.time()

    try:
        # 3. Create the compressed tar archive.
        #    The 'w:gz' mode tells tarfile to create a new archive ('w') and
        #    compress it with gzip ('gz'). This is the simplest, most direct way.
        with tarfile.open(output_filename, 'w:gz') as tar:
            # Add the entire folder to the tar archive.
            # arcname makes the archive contents relative to the folder itself.
            tar.add(abs_folder_path, arcname=folder_name)
    
    except Exception as e:
        print(f"\nAn error occurred during compression: {e}")
        # Clean up partial file if an error occurs
        if os.path.exists(output_filename):
            os.remove(output_filename)
        sys.exit(1)

    end_time = time.time()
    
    # 4. Report results
    original_size = sum(os.path.getsize(os.path.join(dirpath, filename)) for dirpath, _, filenames in os.walk(abs_folder_path) for filename in filenames)
    compressed_size = os.path.getsize(output_filename)
    ratio = original_size / compressed_size if compressed_size > 0 else 0
    duration = end_time - start_time
    
    print("\nCompression successful!")
    print(f"  - Original size:    {original_size / 1e6:.2f} MB")
    print(f"  - Compressed size:  {compressed_size / 1e6:.2f} MB")
    print(f"  - Compression ratio: {ratio:.2f}:1")
    print(f"  - Time taken:       {duration:.2f} seconds")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python compress_folder.py <path_to_folder>")
        print("Example: python compress_folder.py ./my_project")
        sys.exit(1)
    
    folder_to_compress = sys.argv[1]
    compress_folder_gzip(folder_to_compress)

