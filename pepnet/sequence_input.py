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

from serializable import Serializable
import keras.backend as K

from .nn_helpers import (
    aligned_convolutions,
    embedding,
    make_vector_sequence_input,
    make_index_sequence_input,
    local_max_pooling,
    global_max_and_mean_pooling,
    flatten,
    recurrent_layers,
    highway_layers,
    dense_layers
)
from .encoder import Encoder

class SequenceInput(Serializable):
    def __init__(
            self,
            length,
            name=None,
            variable_length=False,
            mask_zero=None,
            # embedding of symbol indices into vectors
            encoding="onehot",
            add_start_tokens=False,
            add_stop_tokens=False,
            add_normalized_position=False,
            add_normalized_centrality=False,
            return_sequences=False,
            # embedding
            embedding_dim=32,
            embedding_dropout=0,
            # convolutional layers
            conv_filter_sizes=[],
            repeat_conv_layers=1,
            conv_dropout=0,
            conv_batch_normalization=False,
            conv_activation="linear",
            conv_weight_source=None,
            pool_size=3,
            pool_stride=2,
            # RNN
            rnn_layer_sizes=[],
            rnn_type="lstm",
            rnn_bidirectional=True,

            # global pooling of conv or RNN outputs
            global_pooling=False,
            global_pooling_batch_normalization=False,
            global_pooling_dropout=0,
            # transform global pooling representation with
            # dense layers
            dense_layer_sizes=[],
            dense_activation="relu",
            dense_dropout=0.25,
            dense_batch_normalization=False,
            # highway layers
            n_highway_layers=0,
            highway_activation="tanh",
            highway_batch_normalization=False,
            highway_dropout=0,):
        """
        Parameters
        ----------
        length : int
            Maximum length of sequence

        name : str
            Name of input sequence

        variable_length : bool
            Do we expect padding '-' characters in the input?

        encoding : {"embedding", "onehot", "blosum", "pmbec"}
            How are symbols represented?
                - embedding: learned vector embedding
                - onehot: binary vector
                - blosum62: rows of BLOSUM62 matrix
                - pmbec: rows of PMBEC matrix

        add_start_tokens : bool
            Add "^" token to start of each sequence

        add_stop_tokens : bool
            Add "$" token to end of each sequence

        embedding_dim : int
            How many dimensions in the symbol embedding
            (only used for index encoding)

        embedding_dropout : float
            What fraction of symbol representations are randomly set to 0
            during training?

        conv_filter_sizes : list of dict
            List whose elements describe to convolutional layers. Each
            element of the list is a dictionary whose keys are filter widths
            and whose values are the number of filters associated with that
            width.

        repeat_conv_layers : int
            Number of times to repeat convolutional layers

        conv_dropout : float
            Fraction of convolutional activations to randomly set to 0 during
            training

        conv_batch_normalization : bool
            Apply batch normalization between convolutional layers

        conv_weight_source : tensor, optional
            Determine weights of the convolution as a function of this
            tensor (rather than learning parameters separately)

        pool_size : int
            If using more than one convolutional layer, how many timesteps
            from a previous layer get combined via maxpooling before the next
            layer.

        pool_stride : int
            If using more than one convolutional layer, stride of the max
            pooling.

        rnn_layer_sizes : list of int
            Dimensionality of each RNN layer, defaults no RNN layers

        rnn_type : {"lstm", "gru"}
            Whether to use GRU or LSTM models for each RNN layer

        rnn_bidirectional : bool
            Use bidirectional RNNs

        return_sequences : bool
            Should final output of RNN layers be same length as input sequence
            or summarized to last output activation.

        global_pooling : bool
            Pool (mean & max) activations across sequence length

        global_pooling_batch_normalization : bool
            Apply BatchNormalization after global pooling

        global_pooling_dropout : float
            Fraction of entries to randomly drop during training after
            global pooling

        dense_layer_sizes : list of int
            Dimensionality of dense transformations after convolutional
            and recurrent layers

        dense_activation: str
            Activation function to use after each dense layer

        dense_dropout : float
            Fraction of dense output values to drop during training

        dense_batch_normalization : bool
            Apply batch normalization between hidden layers

        n_highway_layers : int
            Number of highway layers to use after dense layers

        highway_batch_normalization : bool
            Apply BatchNormalization after final highway layer

        highway_dropout : float
            Apply dropout after final highway layer

        highway_activation : str
            Activation function of each layer in the highway network
        """
        self.name = name
        self.length = length
        if encoding not in {"embedding", "onehot", "blosum", "pmbec"}:
            raise ValueError("Invalid encoding: %s" % encoding)
        self.encoding = encoding
        self.add_start_tokens = add_start_tokens
        self.add_stop_tokens = add_stop_tokens
        self.variable_length = variable_length
        self.padded_length = (
            self.length + self.add_start_tokens + self.add_stop_tokens)

        self.add_normalized_position = add_normalized_position
        self.add_normalized_centrality = add_normalized_centrality

        self.encoder = Encoder(
            variable_length_sequences=self.variable_length,
            add_start_tokens=self.add_start_tokens,
            add_stop_tokens=self.add_stop_tokens,
            add_normalized_position=add_normalized_position,
            add_normalized_centrality=add_normalized_centrality)

        self.n_symbols = len(self.encoder.tokens)
        self.extra_input_dims = (
             int(add_normalized_position) +
            int(add_normalized_centrality))
        if self.encoding == "embedding":
            self.n_input_dims = None
            assert self.extra_input_dims is None
        elif self.encoding == "onehot":
            self.n_input_dims = self.n_symbols + self.extra_input_dims
        else:
            self.n_input_dims = 20 + self.extra_input_dims

        if mask_zero is None:
            mask_zero = variable_length

        self.mask_zero = mask_zero

        self.embedding_dim = embedding_dim
        self.embedding_dropout = embedding_dropout

        self.conv_filter_sizes = conv_filter_sizes
        self.repeat_conv_layers = repeat_conv_layers
        self.conv_dropout = conv_dropout
        self.conv_batch_normalization = conv_batch_normalization
        self.conv_activation = conv_activation
        self.conv_weight_source = conv_weight_source
        self.pool_size = pool_size
        self.pool_stride = pool_stride

        self.rnn_layer_sizes = rnn_layer_sizes
        self.rnn_type = rnn_type
        self.rnn_bidirectional = rnn_bidirectional
        self.return_sequences = return_sequences

        self.global_pooling = global_pooling
        self.global_pooling_batch_normalization = global_pooling_batch_normalization
        self.global_pooling_dropout = global_pooling_dropout

        # Dense layers after all temporal processing
        self.dense_layer_sizes = dense_layer_sizes
        self.dense_activation = dense_activation
        self.dense_dropout = dense_dropout
        self.dense_batch_normalization = dense_batch_normalization

        # Highway network after dense layers
        self.n_highway_layers = n_highway_layers
        self.highway_batch_normalization = highway_batch_normalization
        self.highway_dropout = highway_dropout
        self.highway_activation = highway_activation

    def _build_input(self):
        if self.encoding == "embedding":
            return make_index_sequence_input(
                name=self.name, length=self.padded_length)
        else:
            return make_vector_sequence_input(
                name=self.name,
                length=self.padded_length,
                n_dims=self.n_input_dims)


    def _build_embedding(self, input_object):
        if self.encoding == "embedding":
            if self.embedding_dim <= 0:
                raise ValueError(
                    "Invalid embedding dim: %d" % self.embedding_dim)
            return embedding(
                input_object,
                n_symbols=self.n_symbols,
                output_dim=self.embedding_dim,
                mask_zero=self.mask_zero,
                dropout=self.embedding_dropout)
        else:
            return input_object

    def _build_conv(self, value):
        if self.conv_filter_sizes:
            if isinstance(self.conv_filter_sizes, dict):
                # if only one dictionary is given, then treat it as a single
                # layer
                conv_filter_sizes = [self.conv_filter_sizes]
            else:
                conv_filter_sizes = self.conv_filter_sizes
            conv_weight_source = self.conv_weight_source
            if conv_weight_source is not None and isinstance(
                    conv_weight_source, SequenceInput):
                conv_weight_source = conv_weight_source.build()[1]

            conv_layer_index = 0
            n_conv_layers = self.repeat_conv_layers * len(conv_filter_sizes)
            for _ in range(self.repeat_conv_layers):
                for conv_layer_dict in conv_filter_sizes:
                    if not isinstance(conv_layer_dict, dict):
                        raise ValueError((
                            "Each element of conv_filter_sizes must be a "
                            "{width: num_filters} dictionary, "
                            "got %s : %s instead." % (
                                conv_layer_dict, type(conv_layer_dict))))
                    pool_size = conv_layer_dict.pop("pool_size", self.pool_size)
                    pool_stride = conv_layer_dict.pop(
                        "pool_stride", self.pool_stride)
                    batch_normalization = conv_layer_dict.pop(
                        "batch_normalization", self.conv_batch_normalization)
                    activation = conv_layer_dict.pop(
                        "activation", self.conv_activation)
                    dropout = conv_layer_dict.pop("dropout", self.conv_dropout)
                    maxpooling = (pool_size > 1) or (pool_stride > 1)

                    if len(conv_layer_dict) == 0:
                        # if no convolution sizes specified in this layer, then
                        # skip it
                        continue

                    value = aligned_convolutions(
                        value,
                        filter_sizes=list(conv_layer_dict.keys()),
                        output_dim=conv_layer_dict,
                        dropout=dropout,
                        batch_normalization=batch_normalization,
                        activation=activation,
                        weight_source=conv_weight_source)

                    conv_layer_index += 1

                    if maxpooling and (conv_layer_index < n_conv_layers):
                        # add max pooling for all layers before the last
                        value = local_max_pooling(
                            value,
                            size=pool_size,
                            stride=pool_stride)
        return value

    def _build_rnn(self, value):
        if isinstance(self.rnn_layer_sizes, int):
            rnn_layer_sizes = [self.rnn_layer_sizes]
        else:
            rnn_layer_sizes = self.rnn_layer_sizes

        if len(rnn_layer_sizes) > 0:
            value = recurrent_layers(
                value=value,
                layer_sizes=rnn_layer_sizes,
                rnn_type=self.rnn_type,
                bidirectional=self.rnn_bidirectional,
                return_sequences=self.return_sequences)
        return value

    def _build_global_pooling(self, value):
        if self.global_pooling:
            value = global_max_and_mean_pooling(
                value,
                batch_normalization=self.global_pooling_batch_normalization,
                dropout=self.global_pooling_dropout)
        return value

    def _build_dense(self, value):
        if K.ndim(value) > 2 and not self.return_sequences:
            value = flatten(value, drop_mask=self.mask_zero)

        value = dense_layers(
            value,
            layer_sizes=self.dense_layer_sizes,
            activation=self.dense_activation,
            dropout=self.dense_dropout,
            batch_normalization=self.dense_batch_normalization)
        return value

    def _build_highway(self, value):
        if K.ndim(value) > 2 and not self.return_sequences:
            value = flatten(value, drop_mask=self.mask_zero)
        if self.n_highway_layers:
            value = highway_layers(
                value,
                activation=self.highway_activation,
                n_layers=self.n_highway_layers,
                dropout=self.highway_dropout,
                batch_normalization=self.highway_batch_normalization)
        return value

    def build(self):
        input_object = self._build_input()
        value = self._build_embedding(input_object)
        value = self._build_conv(value)
        value = self._build_rnn(value)
        value = self._build_global_pooling(value)
        value = self._build_dense(value)
        value = self._build_highway(value)
        return input_object, value

    def encode(self, peptides):
        if self.encoding == "embedding":
            fn = self.encoder.encode_index_array
        elif self.encoding == "onehot":
            fn = self.encoder.encode_onehot
        elif self.encoding == "pmbec":
            fn = self.encoder.encode_pmbec
        elif self.encoding == "blosum":
            fn = self.encoder.encode_blosum
        return fn(peptides, max_peptide_length=self.length)

    @classmethod
    def from_dict(cls, config_dict):
        """
        JSON serialization changes int keys of dictionaries to strings,
        so convert those back to integers.
        """
        conv_filter_sizes_with_integer_keys = []
        for layer_dictionary in config_dict.pop("conv_filter_sizes"):
            conv_filter_sizes_with_integer_keys.append(
                {int(k): int(v) for (k, v) in layer_dictionary.items()})
        config_dict["conv_filter_sizes"] = conv_filter_sizes_with_integer_keys
        return cls(**config_dict)
