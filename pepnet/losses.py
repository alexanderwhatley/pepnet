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


import keras.backend as K
from tensorflow import debugging 

def positive_only_mse(y_true, y_pred):
    """
    Mean-squared error loss function that ignores negative values of y_pred.
    Using this as a stop-gap until I can figure out how to avoid the mess
    of explicitly passing an output mask as an Input to a keras model.
    """
    diff = y_pred - y_true
    squared = K.square(diff)
    mask = y_pred >= 0
    squared *= K.cast(mask, "float32")
    return K.mean(squared, axis=-1)

def masked_mse(y_true, y_pred):
    mask = debugging.is_nan(y_true)
    diff = y_pred - y_true
    squared = K.square(diff)
    sum_squared_error = K.sum(
        K.switch(mask, K.zeros(K.shape(squared)), squared),
        axis=-1)
    n_valid_per_sample = K.sum(K.cast(~mask, dtype='float32'), axis=-1)
    return sum_squared_error / n_valid_per_sample

def masked_binary_crossentropy(y_true, y_pred):
    mask = debugging.is_nan(y_true)
    cross_entropy_values = K.binary_crossentropy(
        output=y_pred,
        target=y_true)
    sum_cross_entropy_values = K.sum(
        K.switch(mask, K.zeros(K.shape(cross_entropy_values)), cross_entropy_values), axis=-1)
    n_valid_per_sample = K.sum(K.cast(~mask, dtype='float32'), axis=-1)
    return sum_cross_entropy_values / n_valid_per_sample
