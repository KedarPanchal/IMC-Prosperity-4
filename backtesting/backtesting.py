import sys
import subprocess


def main():
    subprocess.run(["prosperity4btx", *sys.argv[1:]])


if __name__ == "__main__":
    main()
