"""
Driver program for training and evaluation.
"""
import argparse
import logging

import numpy as np
import random
import torch
from torch.autograd import Variable
import torch.nn as nn
import torch.optim as O

from datasets import get_dataset
from metrics.pearson_correlation import PearsonCorrelation
from metrics.spearman_correlation import SpearmanCorrelation
from models import get_model
from runners import Runner


def y_to_score(y, batch):
    num_classes = batch.relatedness_score.size(1)
    predict_classes = Variable(torch.arange(1, num_classes + 1).expand(len(batch.id), num_classes))
    return (predict_classes * y.exp()).sum(dim=1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sentence similarity models')
    parser.add_argument('--model', default='sif', choices=['sif'], help='Model to use')
    parser.add_argument('--dataset', default='sick', choices=['sick'], help='Dataset to use')
    parser.add_argument('--batch-size', type=int, default=64, help='Batch size')
    parser.add_argument('--epochs', type=int, default=15, help='Number of epochs')
    parser.add_argument('--lr', type=float, default=2e-4, help='Learning rate')
    parser.add_argument('--seed', type=int, default=1234, help='Seed for reproducibility')
    parser.add_argument('--device', type=int, default=0, help='Device, -1 for CPU')

    # Special options for SIF model
    parser.add_argument('--unsupervised', action='store_true', default=False, help='Set this flag to use unsupervised mode.')
    parser.add_argument('--alpha', type=float, default=1e-3, help='Smoothing term for smooth inverse frequency baseline model')
    parser.add_argument('--no-remove-special-direction', action='store_true', default=False, help='Set to not remove projection onto first principal component')
    parser.add_argument('--frequency-dataset', default='enwiki', choices=['train', 'enwiki'])

    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if args.device != -1:
        torch.cuda.manual_seed(args.seed)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    dataset_cls, train_loader, dev_loader, test_loader, embedding = get_dataset(args)
    model = get_model(args, dataset_cls, embedding)

    if args.dataset == 'sick':
        model.populate_word_frequency_estimation(train_loader)

        loss_fn = nn.KLDivLoss()
        metrics = {
            'pearson': PearsonCorrelation(),
            'spearman': SpearmanCorrelation()
        }
    else:
        raise ValueError(f'Unrecognized dataset: {args.dataset}')

    optimizer = O.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr, weight_decay=3e-4)
    runner = Runner(model, loss_fn, metrics, optimizer, y_to_score, args.device, None)
    runner.run(args.epochs, train_loader, dev_loader, test_loader, 1000)
