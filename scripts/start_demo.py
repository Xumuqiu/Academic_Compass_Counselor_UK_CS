"""Start the local template demo explicitly, without making model requests."""
import os


def main():
    os.environ['COUNSELOR_MODE'] = 'demo'
    from counselor.server import main as serve
    serve()


if __name__ == '__main__':
    main()
