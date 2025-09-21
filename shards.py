import sys
import os
import json

def create_shard_files(num_shards: int):
    """
    Generates a specified number of shard configuration files in a 'shards' directory.

    Args:
        num_shards: The total number of shard files to create.
    """
    output_dir = "shards"
    
    try:
        # Create the 'shards' directory. The `exist_ok=True` flag prevents
        # an error if the directory already exists.
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        print(f"Error: Could not create directory '{output_dir}'. {e}")
        sys.exit(1)

    # Loop from 0 to num_shards - 1 to create each file.
    for shard_id in range(num_shards):
        # Define the data structure for the JSON content.
        data = {
            "id": shard_id,
            "count": num_shards
        }
        
        # Construct the full path for the output file (e.g., shards/0.json).
        file_path = os.path.join(output_dir, f"{shard_id}.json")
        
        # Write the data to the file. 'with open' ensures the file is closed properly.
        try:
            with open(file_path, 'w') as f:
                # json.dump writes the dictionary to the file in JSON format.
                # indent=4 makes the JSON nicely formatted and human-readable.
                json.dump(data, f, indent=4)
        except IOError as e:
            print(f"Error: Could not write to file '{file_path}'. {e}")
            sys.exit(1)

    print(f"✅ Successfully generated {num_shards} shard files in the '{output_dir}/' directory.")

if __name__ == "__main__":
    # --- Argument Parsing ---
    # Check if exactly one command-line argument was provided.
    if len(sys.argv) != 2:
        print("Usage: python generate_shards.py <number_of_shards>")
        sys.exit(1)
    
    # --- Argument Validation ---
    # Try to convert the argument to an integer and check if it's positive.
    try:
        number_of_shards = int(sys.argv[1])
        if number_of_shards <= 0:
            raise ValueError()
    except ValueError:
        print("Error: Please provide a positive integer for the number of shards.")
        sys.exit(1)
    
    # --- Run the main function ---
    create_shard_files(number_of_shards)