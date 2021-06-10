# Copyright (c) 2021 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy
from . import cv
from .cv.models.utils.visualize import visualize_detection, draw_pr_curve
from paddlex.cv.transforms import det_transforms
from paddlex.cv.transforms.operators import _NormalizeBox, _PadBox, _BboxXYXY2XYWH
from paddlex.cv.transforms.batch_operators import BatchCompose, BatchRandomResize, BatchRandomResizeByShort, \
    _BatchPadding, _Gt2YoloTarget
import paddlex.utils.logging as logging

transforms = det_transforms

visualize = visualize_detection
draw_pr_curve = draw_pr_curve


class FasterRCNN(cv.models.FasterRCNN):
    def __init__(self,
                 num_classes=81,
                 backbone='ResNet50',
                 with_fpn=True,
                 aspect_ratios=[0.5, 1.0, 2.0],
                 anchor_sizes=[32, 64, 128, 256, 512],
                 with_dcn=None,
                 rpn_cls_loss=None,
                 rpn_focal_loss_alpha=None,
                 rpn_focal_loss_gamma=None,
                 rcnn_bbox_loss=None,
                 rcnn_nms=None,
                 keep_top_k=100,
                 nms_threshold=0.5,
                 score_threshold=0.05,
                 softnms_sigma=None,
                 bbox_assigner=None,
                 fpn_num_channels=256,
                 input_channel=None,
                 rpn_batch_size_per_im=256,
                 rpn_fg_fraction=0.5,
                 test_pre_nms_top_n=None,
                 test_post_nms_top_n=1000):
        if with_dcn is not None:
            logging.warning(
                "`with_dcn` is deprecated in PaddleX 2.0 and won't take effect. Defaults to False."
            )
        if rpn_cls_loss is not None:
            logging.warning(
                "`rpn_cls_loss` is deprecated in PaddleX 2.0 and won't take effect. "
                "Defaults to 'SigmoidCrossEntropy'.")
        if rpn_focal_loss_alpha is not None or rpn_focal_loss_gamma is not None:
            logging.warning(
                "Focal loss is deprecated in PaddleX 2.0."
                " `rpn_focal_loss_alpha` and `rpn_focal_loss_gamma` won't take effect."
            )
        if rcnn_bbox_loss is not None:
            logging.warning(
                "`rcnn_bbox_loss` is deprecated in PaddleX 2.0 and won't take effect. "
                "Defaults to 'SmoothL1Loss'")
        if rcnn_nms is not None:
            logging.warning(
                "MultiClassSoftNMS is deprecated in PaddleX 2.0. "
                "`rcnn_nms` and `softnms_sigma` won't take effect. MultiClassNMS will be used by default"
            )
        if bbox_assigner is not None:
            logging.warning(
                "`bbox_assigner` is deprecated in PaddleX 2.0 and won't take effect. "
                "Defaults to 'BBoxAssigner'")
        if input_channel is not None:
            logging.warning(
                "`input_channel` is deprecated in PaddleX 2.0 and won't take effect. Defaults to 3."
            )
        if isinstance(anchor_sizes[0], int):
            anchor_sizes = [[size] for size in anchor_sizes]
        super(FasterRCNN, self).__init__(
            num_classes=num_classes - 1,
            backbone=backbone,
            with_fpn=with_fpn,
            aspect_ratios=aspect_ratios,
            anchor_sizes=anchor_sizes,
            keep_top_k=keep_top_k,
            nms_threshold=nms_threshold,
            score_threshold=score_threshold,
            fpn_num_channels=fpn_num_channels,
            rpn_batch_size_per_im=rpn_batch_size_per_im,
            rpn_fg_fraction=rpn_fg_fraction,
            test_pre_nms_top_n=test_pre_nms_top_n,
            test_post_nms_top_n=test_post_nms_top_n)


class YOLOv3(cv.models.YOLOv3):
    def __init__(self,
                 num_classes=80,
                 backbone='MobileNetV1',
                 anchors=None,
                 anchor_masks=None,
                 ignore_threshold=0.7,
                 nms_score_threshold=0.01,
                 nms_topk=1000,
                 nms_keep_topk=100,
                 nms_iou_threshold=0.45,
                 label_smooth=False,
                 train_random_shapes=[
                     320, 352, 384, 416, 448, 480, 512, 544, 576, 608
                 ],
                 input_channel=None):
        if input_channel is not None:
            logging.warning(
                "`input_channel` is deprecated in PaddleX 2.0 and won't take effect. Defaults to 3."
            )
        if anchors is None:
            anchors = [[10, 13], [16, 30], [33, 23], [30, 61], [62, 45],
                       [59, 119], [116, 90], [156, 198], [373, 326]]
        if anchor_masks is None:
            anchor_masks = [[6, 7, 8], [3, 4, 5], [0, 1, 2]]
        super(YOLOv3, self).__init__(
            num_classes=num_classes,
            backbone=backbone,
            anchors=anchors,
            anchor_masks=anchor_masks,
            ignore_threshold=ignore_threshold,
            nms_score_threshold=nms_score_threshold,
            nms_topk=nms_topk,
            nms_keep_topk=nms_keep_topk,
            nms_iou_threshold=nms_iou_threshold,
            label_smooth=label_smooth)
        self.train_random_shapes = train_random_shapes

    def _compose_batch_transform(self, transforms, mode='train'):
        if mode == 'train':
            default_batch_transforms = [
                _BatchPadding(pad_to_stride=-1), _NormalizeBox(),
                _PadBox(getattr(self, 'num_max_boxes', 50)), _BboxXYXY2XYWH(),
                _Gt2YoloTarget(
                    anchor_masks=self.anchor_masks,
                    anchors=self.anchors,
                    downsample_ratios=getattr(self, 'downsample_ratios',
                                              [32, 16, 8]),
                    num_classes=self.num_classes)
            ]
        else:
            default_batch_transforms = [_BatchPadding(pad_to_stride=-1)]
        if mode == 'eval' and self.metric == 'voc':
            collate_batch = False
        else:
            collate_batch = True

        custom_batch_transforms = []
        random_shape_defined = False
        for i, op in enumerate(transforms.transforms):
            if isinstance(op, (BatchRandomResize, BatchRandomResizeByShort)):
                if mode != 'train':
                    raise Exception(
                        "{} cannot be present in the {} transforms. ".format(
                            op.__class__.__name__, mode) +
                        "Please check the {} transforms.".format(mode))
                custom_batch_transforms.insert(0, copy.deepcopy(op))
                random_shape_defined = True
        if not random_shape_defined:
            default_batch_transforms.insert(
                0,
                BatchRandomResize(
                    target_sizes=self.train_random_shapes, interp='RANDOM'))

        batch_transforms = BatchCompose(
            custom_batch_transforms + default_batch_transforms,
            collate_batch=collate_batch)

        return batch_transforms


class PPYOLO(cv.models.PPYOLO):
    def __init__(
            self,
            num_classes=80,
            backbone='ResNet50_vd_ssld',
            with_dcn_v2=None,
            # YOLO Head
            anchors=None,
            anchor_masks=None,
            use_coord_conv=True,
            use_iou_aware=True,
            use_spp=True,
            use_drop_block=True,
            scale_x_y=1.05,
            # PPYOLO Loss
            ignore_threshold=0.7,
            label_smooth=False,
            use_iou_loss=True,
            # NMS
            use_matrix_nms=True,
            nms_score_threshold=0.01,
            nms_topk=1000,
            nms_keep_topk=100,
            nms_iou_threshold=0.45,
            train_random_shapes=[
                320, 352, 384, 416, 448, 480, 512, 544, 576, 608
            ],
            input_channel=None):
        if backbone == 'ResNet50_vd_ssld':
            backbone = 'ResNet50_vd_dcn'
        if with_dcn_v2 is not None:
            logging.warning(
                "`with_dcn_v2` is deprecated in PaddleX 2.0 and will not take effect. "
                "To use backbone with deformable convolutional networks, "
                "please specify in `backbone_name`. "
                "Currently the only backbone with dcn is 'ResNet50_vd_dcn'.")
        if input_channel is not None:
            logging.warning(
                "`input_channel` is deprecated in PaddleX 2.0 and won't take effect. Defaults to 3."
            )
        super(PPYOLO, self).__init__(
            num_classes=num_classes,
            backbone=backbone,
            anchors=anchors,
            anchor_masks=anchor_masks,
            use_coord_conv=use_coord_conv,
            use_iou_aware=use_iou_aware,
            use_spp=use_spp,
            use_drop_block=use_drop_block,
            scale_x_y=scale_x_y,
            ignore_threshold=ignore_threshold,
            label_smooth=label_smooth,
            use_iou_loss=use_iou_loss,
            use_matrix_nms=use_matrix_nms,
            nms_score_threshold=nms_score_threshold,
            nms_topk=nms_topk,
            nms_keep_topk=nms_keep_topk,
            nms_iou_threshold=nms_iou_threshold)
        self.train_random_shapes = train_random_shapes

    def _compose_batch_transform(self, transforms, mode='train'):
        if mode == 'train':
            default_batch_transforms = [
                _BatchPadding(pad_to_stride=-1), _NormalizeBox(),
                _PadBox(getattr(self, 'num_max_boxes', 50)), _BboxXYXY2XYWH(),
                _Gt2YoloTarget(
                    anchor_masks=self.anchor_masks,
                    anchors=self.anchors,
                    downsample_ratios=getattr(self, 'downsample_ratios',
                                              [32, 16, 8]),
                    num_classes=self.num_classes)
            ]
        else:
            default_batch_transforms = [_BatchPadding(pad_to_stride=-1)]
        if mode == 'eval' and self.metric == 'voc':
            collate_batch = False
        else:
            collate_batch = True

        custom_batch_transforms = []
        random_shape_defined = False
        for i, op in enumerate(transforms.transforms):
            if isinstance(op, (BatchRandomResize, BatchRandomResizeByShort)):
                if mode != 'train':
                    raise Exception(
                        "{} cannot be present in the {} transforms. ".format(
                            op.__class__.__name__, mode) +
                        "Please check the {} transforms.".format(mode))
                custom_batch_transforms.insert(0, copy.deepcopy(op))
                random_shape_defined = True
        if not random_shape_defined:
            default_batch_transforms.insert(
                0,
                BatchRandomResize(
                    target_sizes=self.train_random_shapes, interp='RANDOM'))

        batch_transforms = BatchCompose(
            custom_batch_transforms + default_batch_transforms,
            collate_batch=collate_batch)

        return batch_transforms
