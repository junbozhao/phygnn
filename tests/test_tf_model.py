"""
Tests for basic tensorflow model functionality and execution.
"""
# pylint: disable=W0613
import numpy as np
import os
import pandas as pd
import pytest
import shutil
import tensorflow as tf

from phygnn import TESTDATADIR
from phygnn.model_interfaces.tf_model import TfModel

FPATH = os.path.join(TESTDATADIR, '_temp_model')
FPATH_JSON = os.path.join(TESTDATADIR, '_temp_model.json')
if not os.path.exists(FPATH):
    os.mkdir(FPATH)

s = 0
np.random.seed(s)
tf.random.set_seed(s)

N = 100
A = np.linspace(-1, 1, N)
B = np.linspace(-1, 1, N)
A, B = np.meshgrid(A, B)
A = np.expand_dims(A.flatten(), axis=1)
B = np.expand_dims(B.flatten(), axis=1)

Y = np.sqrt(A ** 2 + B ** 2)
X = np.hstack((A, B))
FEATURES = pd.DataFrame(X, columns=['a', 'b'])
LABELS = pd.DataFrame(Y, columns=['c'])


@pytest.mark.parametrize(
    ('hidden_layers', 'loss'),
    [(None, 0.6),
     ([{'units': 64, 'activation': 'relu', 'name': 'relu1'},
       {'units': 64, 'activation': 'relu', 'name': 'relu2'}], 0.03)])
def test_nn(hidden_layers, loss):
    """Test TfModel """
    model = TfModel.build_trained(FEATURES, LABELS,
                                  hidden_layers=hidden_layers,
                                  epochs=10,
                                  fit_kwargs={"batch_size": 16},
                                  early_stop=False)

    n_l = len(hidden_layers) * 2 + 1 if hidden_layers is not None else 1
    n_w = (len(hidden_layers) + 1) * 2 if hidden_layers is not None else 2
    assert len(model.layers) == n_l
    assert len(model.weights) == n_w
    assert len(model.history) == 10

    test_mae = np.mean(np.abs(model[X].values - Y))
    assert model.history['val_mae'].values[-1] < loss
    assert test_mae < loss


@pytest.mark.parametrize(
    ('normalize', 'loss'),
    [(True, 0.09),
     (False, 0.015),
     ((True, False), 0.01),
     ((False, True), 0.09)])
def test_normalize(normalize, loss):
    """Test TfModel """
    hidden_layers = [{'units': 64, 'activation': 'relu', 'name': 'relu1'},
                     {'units': 64, 'activation': 'relu', 'name': 'relu2'}]
    model = TfModel.build_trained(FEATURES, LABELS,
                                  normalize=normalize,
                                  hidden_layers=hidden_layers,
                                  epochs=10, fit_kwargs={"batch_size": 16},
                                  early_stop=False)

    test_mae = np.mean(np.abs(model[X].values - Y))
    assert model.history['val_mae'].values[-1] < loss
    assert test_mae < loss


def test_complex_nn():
    """Test complex TfModel """
    hidden_layers = [{'units': 64, 'activation': 'relu', 'dropout': 0.01},
                     {'units': 64},
                     {'batch_normalization': {'axis': -1}},
                     {'activation': 'relu'},
                     {'dropout': 0.01}]
    model = TfModel.build_trained(FEATURES, LABELS,
                                  hidden_layers=hidden_layers,
                                  epochs=10, fit_kwargs={"batch_size": 16},
                                  early_stop=False)

    assert len(model.layers) == 8
    assert len(model.weights) == 10

    test_mae = np.mean(np.abs(model[X].values - Y))
    loss = 0.15
    assert model.history['val_mae'].values[-1] < loss
    assert test_mae < loss


def test_save_load():
    """Test the save/load operations of TfModel"""
    hidden_layers = [{'units': 64, 'activation': 'relu', 'name': 'relu1'},
                     {'units': 64, 'activation': 'relu', 'name': 'relu2'}]
    model = TfModel.build_trained(FEATURES, LABELS,
                                  hidden_layers=hidden_layers,
                                  epochs=10, fit_kwargs={"batch_size": 16},
                                  early_stop=False,
                                  save_path=FPATH)
    y_pred = model[X]

    loaded = TfModel.load(FPATH)
    y_pred_loaded = loaded[X]
    np.allclose(y_pred.values, y_pred_loaded.values)
    assert loaded.feature_names == ['a', 'b']
    assert loaded.label_names == ['c']
    shutil.rmtree(FPATH)
    os.remove(FPATH_JSON)


def test_OHE():
    """
    Test one-hot encoding
    """
    ohe_features = FEATURES.copy()
    categories = list('def')
    ohe_features['categorical'] = np.random.choice(categories, len(FEATURES))
    one_hot_categories = {'categorical': categories}

    hidden_layers = [{'units': 64, 'activation': 'relu', 'name': 'relu1'},
                     {'units': 64, 'activation': 'relu', 'name': 'relu2'}]
    model = TfModel.build_trained(ohe_features, LABELS,
                                  one_hot_categories=one_hot_categories,
                                  hidden_layers=hidden_layers,
                                  epochs=10, fit_kwargs={"batch_size": 16},
                                  early_stop=False)

    assert all(np.isin(categories, model.feature_names))
    assert not any(np.isin(categories, model.input_feature_names))
    assert 'categorical' not in model.feature_names
    assert 'categorical' in model.input_feature_names

    x = ohe_features.values
    out = model.predict(x)
    assert 'c' in out


def test_bad_categories():
    """
    Test OHE checks
    """
    hidden_layers = [{'units': 64, 'activation': 'relu', 'name': 'relu1'},
                     {'units': 64, 'activation': 'relu', 'name': 'relu2'}]

    one_hot_categories = {'categorical': list('abc')}
    feature_names = FEATURES.columns.tolist() + ['categorical']
    label_names = 'c'
    with pytest.raises(RuntimeError):
        TfModel.build(feature_names, label_names,
                      one_hot_categories=one_hot_categories,
                      hidden_layers=hidden_layers)

    one_hot_categories = {'categorical': list('cdf')}
    feature_names = FEATURES.columns.tolist() + ['categorical']
    label_names = 'c'
    with pytest.raises(RuntimeError):
        TfModel.build(feature_names, label_names,
                      one_hot_categories=one_hot_categories,
                      hidden_layers=hidden_layers)

    one_hot_categories = {'categorical': list('def')}
    feature_names = FEATURES.columns.tolist() + ['categories']
    label_names = 'c'
    with pytest.raises(RuntimeError):
        TfModel.build(feature_names, label_names,
                      one_hot_categories=one_hot_categories,
                      hidden_layers=hidden_layers)

    one_hot_categories = {'cat1': list('def'), 'cat2': list('fgh')}
    feature_names = FEATURES.columns.tolist() + ['cat1', 'cat2']
    label_names = 'c'
    with pytest.raises(RuntimeError):
        TfModel.build(feature_names, label_names,
                      one_hot_categories=one_hot_categories,
                      hidden_layers=hidden_layers)

    ohe_features = FEATURES.copy()
    categories = list('def')
    ohe_features['categorical'] = np.random.choice(categories, len(FEATURES))
    one_hot_categories = {'categorical': categories}

    model = TfModel.build_trained(ohe_features, LABELS,
                                  one_hot_categories=one_hot_categories,
                                  hidden_layers=hidden_layers,
                                  epochs=10, fit_kwargs={"batch_size": 16},
                                  early_stop=False)

    with pytest.raises(RuntimeError):
        x = ohe_features.values[:, 1:]
        model.predict(x)
