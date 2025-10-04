import os
import argparse
from pathlib import Path

def is_text_file(file_path):
    """Check if a file is likely a text file (source code)"""
    text_extensions = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.scss', 
        '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', 
        '.rs', '.swift', '.kt', '.kts', '.sql', '.sh', '.bash',
        '.md', '.txt', '.json', '.xml', '.yml', '.yaml', '.toml',
        '.ini', '.cfg', '.conf', '.env', '.sol'
    }
    
    # Check file extension
    _, ext = os.path.splitext(file_path)
    if ext.lower() in text_extensions:
        return True
    
    # If no extension or unknown, try to read a small portion
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
        # Check if it's mostly printable ASCII or UTF-8
        text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)))
        return not bool(chunk.translate(None, text_chars))
    except:
        return False

def collect_code_files(root_dir, exclude_dirs=None):
    """Recursively collect all code files from directory"""
    if exclude_dirs is None:
        exclude_dirs = {'.git', '__pycache__', 'node_modules', '.vscode', '.idea'}
    
    code_files = []
    root_path = Path(root_dir)
    
    for file_path in root_path.rglob('*'):
        # Skip if any parent directory is in exclude list
        if any(part in exclude_dirs for part in file_path.parts):
            continue
            
        # Process only files (not directories)
        if file_path.is_file() and is_text_file(str(file_path)):
            code_files.append(file_path)
            
    return code_files

def write_code_file(file_path, output_file):
    """Write a single file's content to output with header"""
    try:
        # Write header with relative path
        output_file.write(f"# {file_path}\n")
        
        # Write file content
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            output_file.write(content)
        
        # Add spacing between files
        output_file.write("\n\n")
        print(f"Added: {file_path}")
        
    except Exception as e:
        print(f"Warning: Could not read {file_path} - {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Consolidate code files into a single text file")
    parser.add_argument("directory", nargs="?", default=".", 
                       help="Directory to scan (default: current directory)")
    parser.add_argument("-o", "--output", default="code.txt",
                       help="Output file name (default: code.txt)")
    args = parser.parse_args()
    
    root_dir = os.path.abspath(args.directory)
    output_file = args.output
    
    if not os.path.exists(root_dir):
        print(f"Error: Directory '{root_dir}' does not exist")
        return
    
    if not os.path.isdir(root_dir):
        print(f"Error: '{root_dir}' is not a directory")
        return
    
    print(f"Scanning directory: {root_dir}")
    print(f"Output file: {output_file}")
    print("-" * 50)
    
    # Collect all code files
    code_files = collect_code_files(root_dir)
    
    if not code_files:
        print("No code files found!")
        return
    
    print(f"Found {len(code_files)} code files")
    
    # Write all files to output
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Codebase export from: {root_dir}\n")
            f.write(f"# Generated on: {os.path.basename(__file__)}\n")
            f.write("#" * 60 + "\n\n")
            
            for file_path in sorted(code_files):
                # Get relative path from root directory
                rel_path = file_path.relative_to(root_dir)
                write_code_file(rel_path, f)
        
        print("-" * 50)
        print(f"Successfully created {output_file}")
        
    except Exception as e:
        print(f"Error writing to output file: {str(e)}")

if __name__ == "__main__":
    main()