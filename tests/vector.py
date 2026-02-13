import numpy as np

if __name__ == '__main__':
    a = np.array(range(256),dtype=np.uint8)
    mask = a > -1
    a[mask] = a[mask] - a[mask] % 25.5
    print((a / 255 * 100).astype(np.uint8))