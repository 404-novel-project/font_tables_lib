import io
import os
import re
import argparse
from time import sleep
import requests
from urllib.parse import urlparse

def download_file(url, folder):
    response = requests.get(url)
    if response.status_code == 200:
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        filename = os.path.join(folder, filename)
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {filename}")
        return True
    else:
        print(f"Failed to download: {url}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Download links from command line input")
    parser.add_argument('input_string', type=str, help="Input string containing links")
    args = parser.parse_args()

    links = re.findall(r'(https?://\S+)', args.input_string)
    if not os.path.exists('sample_font'):
        os.makedirs('sample_font')

    for link in links:
        time = 0
        while not download_file(link, 'sample_font'):
            print("Retrying...")
            sleep(0.6)
            time += 1
            if time > 5:
                print("Failed to download file")
                break
        sleep(1)

if __name__ == "__main__":
    main()
