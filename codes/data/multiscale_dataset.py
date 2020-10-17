import random
import numpy as np
import cv2
import torch
import torch.utils.data as data
import data.util as util
from PIL import Image, ImageOps
from io import BytesIO
import torchvision.transforms.functional as F


# Reads full-quality images and pulls tiles at regular zoom intervals from them. Only usable for training purposes.
class MultiScaleDataset(data.Dataset):
    def __init__(self, opt):
        super(MultiScaleDataset, self).__init__()
        self.opt = opt
        self.data_type = 'img'
        self.tile_size = self.opt['hq_tile_size']
        self.num_scales = self.opt['num_scales']
        self.hq_size_cap = self.tile_size * 2 ** self.num_scales
        self.scale = self.opt['scale']
        self.paths_hq, self.sizes_hq = util.get_image_paths(self.data_type, opt['dataroot'], [1])

    # Selects the smallest dimension from the image and crops it randomly so the other dimension matches. The cropping
    # offset from center is chosen on a normal probability curve.
    def get_square_image(self, image):
        h, w, _ = image.shape
        if h == w:
            return image
        offset = max(min(np.random.normal(scale=.3), 1.0), -1.0)
        if h > w:
            diff = h - w
            center = diff // 2
            top = int(center + offset * (center - 2))
            return image[top:top+w, :, :]
        else:
            diff = w - h
            center = diff // 2
            left = int(center + offset * (center - 2))
            return image[:, left:left+h, :]

    def recursively_extract_patches(self, input_img, result_list, depth):
        if depth >= self.num_scales:
            return
        patch_size = self.hq_size_cap // (2 ** depth)
        # First pull the four sub-patches.
        patches = [input_img[:patch_size, :patch_size],
                   input_img[:patch_size, patch_size:],
                   input_img[patch_size:, :patch_size],
                   input_img[patch_size:, patch_size:]]
        result_list.extend([cv2.resize(p, (self.tile_size, self.tile_size), interpolation=cv2.INTER_AREA) for p in patches])
        for p in patches:
            self.recursively_extract_patches(p, result_list, depth+1)

    def __getitem__(self, index):
        # get full size image
        full_path = self.paths_hq[index % len(self.paths_hq)]
        img_full = util.read_img(None, full_path, None)
        img_full = util.channel_convert(img_full.shape[2], 'RGB', [img_full])[0]
        img_full = util.augment([img_full], True, True)[0]
        img_full = self.get_square_image(img_full)
        img_full = cv2.resize(img_full, (self.hq_size_cap, self.hq_size_cap), interpolation=cv2.INTER_AREA)
        patches_hq = [cv2.resize(img_full, (self.tile_size, self.tile_size), interpolation=cv2.INTER_AREA)]
        self.recursively_extract_patches(img_full, patches_hq, 1)

        # BGR to RGB, HWC to CHW, numpy to tensor
        if patches_hq[0].shape[2] == 3:
            patches_hq = [cv2.cvtColor(p, cv2.COLOR_BGR2RGB) for p in patches_hq]
        patches_hq = [torch.from_numpy(np.ascontiguousarray(np.transpose(p, (2, 0, 1)))).float() for p in patches_hq]
        patches_lq = [torch.nn.functional.interpolate(p.unsqueeze(0), scale_factor=1/self.scale, mode='bilinear').squeeze() for p in patches_hq]

        d = {'LQ': patches_lq, 'HQ': patches_hq, 'GT_path': full_path}
        return d

    def __len__(self):
        return len(self.paths_hq)

class MultiscaleTreeNode:
    def __init__(self, index, parent):
        self.index = index
        self.parent = parent
        self.children = []

    def add_child(self, child):
        self.children.append(child)
        return child


def build_multiscale_patch_index_map(depth):
    if depth < 0:
        return
    root = MultiscaleTreeNode(0, None)
    leaves = []
    _build_multiscale_patch_index_map(depth-1, 1, root, leaves)
    return leaves


def _build_multiscale_patch_index_map(depth, ind, node, leaves):
    subnodes = [node.add_child(MultiscaleTreeNode(ind+i, node)) for i in range(4)]
    ind += 4
    if depth == 1:
        leaves.extend(subnodes)
    else:
        for n in subnodes:
            ind = _build_multiscale_patch_index_map(depth-1, ind, n, leaves)
    return ind


if __name__ == '__main__':
    opt = {
        'name': 'amalgam',
        'dataroot': ['F:\\4k6k\\datasets\\ns_images\\imagesets\\images'],
        'num_scales': 4,
        'scale': 2,
        'hq_tile_size': 128
    }

    import torchvision
    ds = MultiScaleDataset(opt)
    import os
    os.makedirs("debug", exist_ok=True)
    multiscale_tree = build_multiscale_patch_index_map(4)
    for i in range(500, len(ds)):
        quadrant=2
        print(i)
        o = ds[random.randint(0, len(ds))]
        k = 'HQ'
        v = o['HQ']
        #for j, img in enumerate(v):
        #    torchvision.utils.save_image(img.unsqueeze(0), "debug/%i_%s_%i.png" % (i, k, j))
        tree_ind = random.randint(0, len(multiscale_tree))
        node = multiscale_tree[tree_ind]
        depth = 0
        while node is not None:
            torchvision.utils.save_image(v[node.index].unsqueeze(0), "debug/%i_%s_%i.png" % (i, k, depth))
            depth += 1
            node = node.parent