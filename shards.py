import sys
import os
import json

def create_shard_files_for_role(base_dir: str, role: str, num_shards: int):
    """
    Generates shard configuration files for a specific role within a base directory.

    Args:
        base_dir: The single output directory where all files will be stored.
        role: The name of the role, used as a prefix for the output file names.
        num_shards: The total number of shard files to create for this role.
    
    Raises:
        IOError: If a configuration file cannot be written to.
    """
    # Loop to create each shard file, now named with the role as a prefix.
    for shard_id in range(1, num_shards + 1):
        data = {
            "id": shard_id,
            "count": num_shards,
            "role": role # Add role to the config for clarity
        }
        
        # New file naming convention: <role>.<shard_id>.json
        file_name = f"{role}.{shard_id}.json"
        file_path = os.path.join(base_dir, file_name)
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)

    print(f"✅ Generated {num_shards} shard files for role '{role}'.")

def main():
    """
    Main function to parse command-line arguments and generate shard files for
    one or more roles into a single 'shards' directory.
    """
    args = sys.argv[1:]
    output_dir = "shards"

    # --- Argument Parsing and Validation ---
    if not args or len(args) % 2 != 0:
        print("Usage: python generate_shards.py <role1> <num_shards1> [<role2> <num_shards2> ...]")
        print("Example: python generate_shards.py scheduler 10 command_handler 5")
        sys.exit(1)
    
    try:
        # Create the single 'shards' directory once at the beginning.
        os.makedirs(output_dir, exist_ok=True)

        # Process the arguments in pairs (role, num_shards).
        for i in range(0, len(args), 2):
            role = args[i]
            num_shards_str = args[i+1]
            
            # --- Validate the number of shards for the current role ---
            try:
                num_shards = int(num_shards_str)
                if num_shards <= 0:
                    raise ValueError()
            except ValueError:
                print(f"Error: Invalid number of shards '{num_shards_str}' for role '{role}'. Please provide a positive integer.")
                sys.exit(1)
            
            # --- Generate the files for the current valid role ---
            create_shard_files_for_role(output_dir, role, num_shards)

    except (OSError, IOError) as e:
        print(f"A file system error occurred: {e}")
        sys.exit(1)
    
    print(f"\nAll shard files generated successfully in the './{output_dir}/' directory.")

if __name__ == "__main__":
    main()


