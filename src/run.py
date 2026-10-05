"""From project root: python src/run.py"""
from generate_data import generate
from analyze import analyze

if __name__ == '__main__':
    print(analyze(generate()))
