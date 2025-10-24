#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json
import mimetypes

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

class UploadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            with open('index.html', 'rb') as f:
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(f.read())
        
        elif self.path == '/slideshow':
            with open('slideshow.html', 'rb') as f:
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(f.read())
        
        elif self.path == '/favicon.ico':
            # Check if favicon.ico exists, otherwise return empty response
            if os.path.exists('favicon.ico'):
                with open('favicon.ico', 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'image/x-icon')
                    self.end_headers()
                    self.wfile.write(f.read())
            else:
                # Return a 204 No Content if favicon doesn't exist
                self.send_response(204)
                self.end_headers()
        
        elif self.path == '/api/images':
            # Return list of images in pictures folder
            pictures_dir = 'pictures'
            if os.path.exists(pictures_dir):
                images = [f for f in os.listdir(pictures_dir) 
                         if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
                images.sort()  # Sort alphabetically
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(images).encode())
            else:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps([]).encode())
        
        elif self.path.startswith('/pictures/'):
            # Decode URL-encoded path (handles spaces and special characters)
            decoded_path = url_decode(self.path[1:])  # Remove leading slash and decode
            if os.path.exists(decoded_path) and os.path.isfile(decoded_path):
                mime_type, _ = mimetypes.guess_type(decoded_path)
                with open(decoded_path, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', mime_type or 'application/octet-stream')
                    self.end_headers()
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
        
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path == '/upload':
            # Create pictures directory if it doesn't exist
            os.makedirs('pictures', exist_ok=True)
            
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_error(400, 'Invalid content type')
                return
            
            # Extract boundary
            boundary = content_type.split('boundary=')[1].strip()
            
            # Read the body
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            
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
                    
                    # Extract original filename
                    filename = 'uploaded_image.jpg'
                    for line in headers.split('\n'):
                        if 'filename=' in line:
                            filename = line.split('filename=')[1].strip().strip('"')
                            break
                    
                    # Save with original filename
                    filepath = os.path.join('pictures', filename)
                    
                    # Handle duplicate filenames
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(filepath):
                        filepath = os.path.join('pictures', f'{base}_{counter}{ext}')
                        counter += 1
                    
                    with open(filepath, 'wb') as f:
                        f.write(file_data)
                    
                    print(f'Saved: {filepath}')
                    
                    # Send proper response
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.send_header('Content-Length', str(len(b'Upload successful')))
                    self.end_headers()
                    self.wfile.write(b'Upload successful')
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
    print('Pictures folder: ./pictures/')
    print('Press Ctrl+C to stop')
    HTTPServer(('', port), UploadHandler).serve_forever()
