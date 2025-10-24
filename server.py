#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json
import mimetypes

# Security settings
MAX_FILE_SIZE = 15 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
PICTURES_DIR = 'pictures'
MAX_FILENAME_LENGTH = 255

def url_decode(s):
    """Decode URL-encoded string manually"""
    result = []
    i = 0
    while i < len(s):
        if s[i] == '%' and i + 2 < len(s):
            try:
                # Convert %XX to character
                hex_chars = s[i+1:i+3]
                char = chr(int(hex_chars, 16))
                result.append(char)
                i += 3
            except ValueError:
                result.append(s[i])
                i += 1
        elif s[i] == '+':
            result.append(' ')
            i += 1
        else:
            result.append(s[i])
            i += 1
    return ''.join(result)

def sanitize_filename(filename):
    """Sanitize filename to prevent directory traversal and other attacks"""
    # Remove any path components
    filename = os.path.basename(filename)
    
    # Remove null bytes
    filename = filename.replace('\x00', '')
    
    # Remove leading dots and spaces
    filename = filename.lstrip('. ')
    
    # If filename is empty after sanitization, use default
    if not filename:
        filename = 'upload.jpg'
    
    # Limit length
    if len(filename) > MAX_FILENAME_LENGTH:
        name, ext = os.path.splitext(filename)
        filename = name[:MAX_FILENAME_LENGTH - len(ext)] + ext
    
    return filename

def is_allowed_file(filename):
    """Check if file extension is allowed"""
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_EXTENSIONS

def is_safe_path(basedir, path):
    """Ensure the path doesn't escape the base directory"""
    basedir = os.path.abspath(basedir)
    path = os.path.abspath(path)
    return path.startswith(basedir)

class UploadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            if os.path.exists('index.html'):
                with open('index.html', 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
        
        elif self.path == '/slideshow':
            if os.path.exists('slideshow.html'):
                with open('slideshow.html', 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
        
        elif self.path == '/favicon.ico':
            if os.path.exists('favicon.ico'):
                with open('favicon.ico', 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'image/x-icon')
                    self.end_headers()
                    self.wfile.write(f.read())
            else:
                self.send_response(204)
                self.end_headers()
        
        elif self.path == '/api/images':
            if os.path.exists(PICTURES_DIR):
                try:
                    images = [f for f in os.listdir(PICTURES_DIR) 
                             if os.path.isfile(os.path.join(PICTURES_DIR, f)) and
                             f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
                    images.sort()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(images).encode())
                except Exception as e:
                    print(f"Error listing images: {e}")
                    self.send_error(500)
            else:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps([]).encode())
        
        elif self.path.startswith('/pictures/'):
            decoded_path = url_decode(self.path[1:])
            full_path = os.path.abspath(decoded_path)
            
            # Security: Ensure path doesn't escape pictures directory
            if not is_safe_path(PICTURES_DIR, full_path):
                self.send_error(403, 'Forbidden')
                return
            
            if os.path.exists(full_path) and os.path.isfile(full_path):
                # Only serve allowed file types
                if not is_allowed_file(full_path):
                    self.send_error(403, 'Forbidden file type')
                    return
                
                mime_type, _ = mimetypes.guess_type(full_path)
                try:
                    with open(full_path, 'rb') as f:
                        self.send_response(200)
                        self.send_header('Content-type', mime_type or 'application/octet-stream')
                        # Prevent browser from executing files
                        self.send_header('X-Content-Type-Options', 'nosniff')
                        self.end_headers()
                        self.wfile.write(f.read())
                except Exception as e:
                    print(f"Error serving file: {e}")
                    self.send_error(500)
            else:
                self.send_error(404)
        
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path == '/upload':
            # Create pictures directory if it doesn't exist
            os.makedirs(PICTURES_DIR, exist_ok=True)
            
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_error(400, 'Invalid content type')
                return
            
            # Check content length
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > MAX_FILE_SIZE:
                self.send_response(413)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'File too large. Maximum size is 10MB.')
                return
            
            if content_length == 0:
                self.send_error(400, 'No content')
                return
            
            # Extract boundary
            try:
                boundary = content_type.split('boundary=')[1].strip()
            except IndexError:
                self.send_error(400, 'Invalid multipart boundary')
                return
            
            # Read the body
            try:
                body = self.rfile.read(content_length)
            except Exception as e:
                print(f"Error reading request body: {e}")
                self.send_error(400, 'Error reading request')
                return
            
            # Parse multipart data
            parts = body.split(f'--{boundary}'.encode())
            
            for part in parts:
                if b'Content-Disposition' in part and b'filename=' in part:
                    # Extract filename
                    header_end = part.find(b'\r\n\r\n')
                    if header_end == -1:
                        continue
                    
                    headers = part[:header_end].decode('utf-8', errors='ignore')
                    file_data = part[header_end + 4:]
                    
                    # Remove trailing boundary markers
                    if file_data.endswith(b'\r\n'):
                        file_data = file_data[:-2]
                    
                    # Validate file size
                    if len(file_data) > MAX_FILE_SIZE:
                        self.send_response(413)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b'File too large')
                        return
                    
                    if len(file_data) == 0:
                        self.send_error(400, 'Empty file')
                        return
                    
                    # Extract and sanitize filename
                    filename = 'uploaded_image.jpg'
                    for line in headers.split('\n'):
                        if 'filename=' in line:
                            filename = line.split('filename=')[1].strip().strip('"')
                            break
                    
                    filename = sanitize_filename(filename)
                    
                    # Check file extension
                    if not is_allowed_file(filename):
                        self.send_response(400)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b'Invalid file type. Only images are allowed.')
                        return
                    
                    # Save with sanitized filename
                    filepath = os.path.join(PICTURES_DIR, filename)
                    
                    # Ensure the final path is safe
                    if not is_safe_path(PICTURES_DIR, filepath):
                        self.send_error(403, 'Invalid file path')
                        return
                    
                    # Handle duplicate filenames
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(filepath):
                        filepath = os.path.join(PICTURES_DIR, f'{base}_{counter}{ext}')
                        counter += 1
                        # Safety check
                        if counter > 10000:
                            self.send_error(500, 'Too many duplicate files')
                            return
                    
                    try:
                        with open(filepath, 'wb') as f:
                            f.write(file_data)
                        
                        print(f'Saved: {filepath} ({len(file_data)} bytes)')
                        
                        # Send proper response
                        self.send_response(200)
                        self.send_header('Content-type', 'text/plain')
                        self.send_header('Content-Length', str(len(b'Upload successful')))
                        self.end_headers()
                        self.wfile.write(b'Upload successful')
                        return
                    except Exception as e:
                        print(f"Error saving file: {e}")
                        self.send_error(500, 'Error saving file')
                        return
            
            # If we got here, no file was found
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'No file uploaded')

if __name__ == '__main__':
    # Get port from environment variable, default to 8080
    port = int(os.environ.get('PORT', 8080))
    
    print(f'Server running on http://localhost:{port}')
    print(f'Upload images: http://localhost:{port}/')
    print(f'View slideshow: http://localhost:{port}/slideshow')
    print(f'Pictures folder: ./{PICTURES_DIR}/')
    print(f'Max file size: {MAX_FILE_SIZE / 1024 / 1024}MB')
    print('Press Ctrl+C to stop')
    HTTPServer(('', port), UploadHandler).serve_forever()
