"""create dataset and dataloader"""
import logging
import torch
import torch.utils.data
from munch import munchify

from utils.util import opt_get


def create_dataloader(dataset, dataset_opt, opt=None, sampler=None, collate_fn=None, shuffle=True):
    phase = dataset_opt['phase']
    if phase == 'train':
        if opt_get(opt, ['dist'], False):
            world_size = torch.distributed.get_world_size()
            num_workers = dataset_opt['n_workers']
            assert dataset_opt['batch_size'] % world_size == 0
            batch_size = dataset_opt['batch_size'] // world_size
        else:
            num_workers = dataset_opt['n_workers']
            batch_size = dataset_opt['batch_size']
        return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=shuffle,
                                           num_workers=num_workers, sampler=sampler, drop_last=True,
                                           pin_memory=True, collate_fn=collate_fn)
    else:
        batch_size = dataset_opt['batch_size'] or 1
        return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0,
                                           pin_memory=True, collate_fn=collate_fn)


def create_dataset(dataset_opt, return_collate=False):
    mode = dataset_opt['mode']
    collate = None

    # datasets for image restoration
    if mode == 'fullimage':
        from data.full_image_dataset import FullImageDataset as D
    elif mode == 'single_image_extensible':
        from data.single_image_dataset import SingleImageDataset as D
    elif mode == 'multi_frame_extensible':
        from data.multi_frame_dataset import MultiFrameDataset as D
    elif mode == 'combined':
        from data.combined_dataset import CombinedDataset as D
    elif mode == 'multiscale':
        from data.multiscale_dataset import MultiScaleDataset as D
    elif mode == 'paired_frame':
        from data.paired_frame_dataset import PairedFrameDataset as D
    elif mode == 'stylegan2':
        from data.stylegan2_dataset import Stylegan2Dataset as D
    elif mode == 'imagefolder':
        from data.image_folder_dataset import ImageFolderDataset as D
    elif mode == 'torch_dataset':
        from data.torch_dataset import TorchDataset as D
    elif mode == 'byol_dataset':
        from data.byol_attachment import ByolDatasetWrapper as D
    elif mode == 'byol_structured_dataset':
        from data.byol_attachment import StructuredCropDatasetWrapper as D
    elif mode == 'random_aug_wrapper':
        from data.byol_attachment import DatasetRandomAugWrapper as D
    elif mode == 'random_dataset':
        from data.random_dataset import RandomDataset as D
    elif mode == 'zipfile':
        from data.zip_file_dataset import ZipFileDataset as D
    elif mode == 'nv_tacotron':
        from data.audio.nv_tacotron_dataset import TextMelLoader as D
        from data.audio.nv_tacotron_dataset import TextMelCollate as C
        from models.tacotron2.hparams import create_hparams
        default_params = create_hparams()
        default_params.update(dataset_opt)
        dataset_opt = munchify(default_params)
        if opt_get(dataset_opt, ['needs_collate'], True):
            collate = C(dataset_opt.n_frames_per_step)
    elif mode == 'gpt_tts':
        from data.audio.gpt_tts_dataset import GptTtsDataset as D
        from data.audio.gpt_tts_dataset import GptTtsCollater as C
        collate = C(dataset_opt)
    elif mode == 'wavfile_clips':
        from data.audio.wavfile_dataset import WavfileDataset as D
    elif mode == 'stop_prediction':
        from models.tacotron2.hparams import create_hparams
        default_params = create_hparams()
        default_params.update(dataset_opt)
        dataset_opt = munchify(default_params)
        from data.audio.stop_prediction_dataset import StopPredictionDataset as D
    elif mode == 'stop_prediction2':
        from data.audio.stop_prediction_dataset_2 import StopPredictionDataset as D
    else:
        raise NotImplementedError('Dataset [{:s}] is not recognized.'.format(mode))
    dataset = D(dataset_opt)

    if return_collate:
        return dataset, collate
    else:
        return dataset
