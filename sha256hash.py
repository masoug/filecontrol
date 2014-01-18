import hashlib, sys

def main(filename):
    hasher = hashlib.sha256()
    with open(filename, "rb") as fd:
        for block in iter(lambda: fd.read(hasher.block_size), b''):
            hasher.update(block)
    print hasher.hexdigest()

if __name__ == "__main__":
    main(sys.argv[1])
