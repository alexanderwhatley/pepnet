# Copyright (c) 2017. Mount Sinai School of Medicine
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import keras.losses

from .helpers import dense_layers, dense
from .numeric import Numeric
from .losses import positive_only_mse

class Output(Numeric):
    """
    Numeric output for neural network.
    """
    def __init__(
            self,
            dim=1,
            activation="linear",
            name=None,
            loss="mse",
            dense_layer_sizes=[],
            dense_activation="relu",
            dense_dropout=0,
            dense_batch_normalization=False,
            transform=None,
            inverse_transform=None,
            mask_negative=False):
        Numeric.__init__(
            self,
            name=name,
            dim=dim,
            dense_layer_sizes=dense_layer_sizes,
            dense_activation=dense_activation,
            dense_dropout=dense_dropout,
            dense_batch_normalization=dense_batch_normalization,
            transform=transform)
        self.activation = activation
        self.loss = loss
        self.inverse_transform = inverse_transform
        self.mask_negative = mask_negative

    def build(self, value):
        hidden = dense_layers(
            value,
            layer_sizes=self.dense_layer_sizes,
            activation=self.dense_activation,
            dropout=self.dense_dropout,
            batch_normalization=self.dense_batch_normalization)
        output = dense(
            hidden,
            dim=self.dim,
            activation=self.activation,
            name=self.name)
        return output

    def decode(self, x):
        if self.inverse_transform:
            return self.inverse_transform(x)
        return x

    @property
    def loss_fn(self):
        """
        If output requires masking then apply it to the loss function,
        otherwise just return the loss function.
        """
        if self.mask_negative:
            if self.loss == "mse":
                return positive_only_mse
            else:
                raise ValueError("No masked loss available for '%s'" % (
                    self.loss,))
        else:
            return keras.losses.deserialize(self.loss)

