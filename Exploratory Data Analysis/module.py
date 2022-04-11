from typing import List, Set, Dict, Tuple, Optional, Any
import warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import fbeta_score, accuracy_score

def load_dataset(filename: str, resample_period :Optional[str]=None) -> pd.DataFrame:
    """
    Loads the dataset
    filename: the path to the file to load
    resample_period: (optional) the reasmple period, if None the default period of 1 second will be used
    returns: a DataFrame containing the dataset
    """
    dataset = pd.read_csv(filename, index_col='datetime').interpolate('linear')
    dataset.index = pd.to_datetime(dataset.index)
    dataset = dataset.asfreq('s')

    if resample_period:
        dataset = dataset.resample(resample_period).nearest()
    
    dataset['hour'] = dataset.index.hour + dataset.index.minute / 60 #+ dataset.index.seconde / 3600

    return dataset


def pick_random_indexes(data: pd.DataFrame, percentage: Optional[float]=0.3) -> pd.DatetimeIndex:
    """
    Returns random indexes from the index of the DataFrame passed in parameter
    data: the DataFrame to use
    percentage: the percentage of indexes to randomly pick
    returns: a DatetimeIndex with random dates
    """
    # tirage de jours aléatoires
    delta_time = data.index[-2] - data.index[0]
    nb_days = int(delta_time.days * percentage)
    random_dates = data.index[0] + pd.to_timedelta(np.random.choice(delta_time.days, nb_days, replace=False), unit='day')

    data_freq = pd.Timedelta(data.index.freq).seconds if data.index.freq else 1
    # définition des indexes test, train
    rand_indexes = pd.DatetimeIndex(np.array([pd.date_range(d, periods=24*60*60/data_freq, freq=data.index.freq) for d in random_dates]).ravel())

    return rand_indexes

def split_train_test_indexes(data: pd.DataFrame, percentage: Optional[float]=0.3) -> Tuple[pd.DatetimeIndex]:
    """
    Generate train and test indexes on a time series by picking random full days
    data: the DataFrame to use
    percentage: the percentage of indexes to randomly pick for the test
    returns: a tuple of DatetimeIndex with random days for the train indexes and test indexes
    """
    # tirage de jours aléatoires
    delta_time = data.index[-2] - data.index[0]
    nb_days = int(delta_time.days * percentage)
    random_dates = data.index[0] + pd.to_timedelta(np.random.choice(delta_time.days, nb_days, replace=False), unit='day')

    data_freq = pd.Timedelta(data.index.freq).seconds if data.index.freq else 1
    # définition des indexes test, train
    test_indexes = pd.DatetimeIndex(np.array([pd.date_range(d, periods=24*60*60/data_freq, freq=data.index.freq) for d in random_dates]).ravel())
    train_indexes = data.index[~np.isin(data.index, test_indexes)]

    return train_indexes, test_indexes

def split_train_test_scale_df(data: pd.DataFrame, features_col:List[str], label_col: Optional[List[str]]=['activity'], percentage: Optional[float]=0.3, scaler: Optional[Any]=StandardScaler()) -> Tuple[np.array]:
    """
    Performs a split train test on a time series by picking random full days and then scales then feature columns
    data: the DataFrame to use
    features_col: a list containing the names of the feature columns
    features_col: a list containing the name of the label column
    percentage: the percentage of indexes to randomly pick for the test
    scale: (optional) the scaler to use
    returns: a tuple consisting of X_train, X_test, y_train, y_test
    """
    # tirage de jours aléatoires
    train_indexes, test_indexes = split_train_test_indexes(data, percentage)

    # on crée un DF normalisé
    data_norm = data[features_col + label_col].copy()

    # on fit le scaler et normalise le jeu de train
    data_norm.loc[train_indexes, features_col] = scaler.fit_transform(data_norm.loc[train_indexes, features_col].values)
    # on normalise le jeu de test
    data_norm.loc[test_indexes, features_col] = scaler.transform(data_norm.loc[test_indexes, features_col].values)

    # on génère les X/y train/test
    X_train, X_test = data_norm.loc[train_indexes, features_col].values, data_norm.loc[test_indexes, features_col].values
    y_train, y_test = data_norm.loc[train_indexes, 'activity'].values, data_norm.loc[test_indexes, 'activity'].values

    return X_train, X_test, y_train, y_test

def generate_scaled_features(data: pd.DataFrame, column_name: Optional[str]='mains', window: Optional[str]='1h', scaler: Optional[Any]=StandardScaler(), fillna_method :Optional[str]='bfill') -> Tuple[pd.DataFrame, List[str], StandardScaler]:
    """
    Generates scaled features for classifications
    data: the DataFrame to use
    column_name: the name of the column with the power data
    window: (optional) the window of time for the rolling transformations
    scaler: (optional) the scaler to use
    fillna_method: (optional) the method to use the fill na values that will occure due to the rolling transformations
    returns: a DataFrame with the old and new features, a list containing the names of the new features columns, and the fitter scaler
    """
    warnings.warn("This function is depreciated, use generate_features and manually scale the features instead", DeprecationWarning)

    # we prepare our features
    data['mains_scaled'] = data[column_name].values.reshape(-1,1)
    data['mean_'+window+'_scaled'] = data[column_name].rolling(window).mean().values.reshape(-1,1)
    data['std_'+window+'_scaled'] = data[column_name].rolling(window).std().values.reshape(-1,1)
    data['maxmin_'+window+'_scaled'] = data[column_name].rolling(window).max().values.reshape(-1,1) - data[column_name].rolling(window).min().values.reshape(-1,1)
    data['peaks_'+window+'_scaled'] = ((data[column_name] - data['mean_'+window]) < 1e-3).astype(int).rolling(window, center=True).sum().values.reshape(-1,1)
    data['hour_scaled'] = data['hour'].values.reshape(-1,1)
    data['weekend'] = data.index.day_of_week.isin([5, 6]).astype(int)

    # we fill the na values with the chosen method
    data = data.fillna(method=fillna_method)

    # we generate a list of the column names generated
    features_col = ['mains_scaled', 'hour_scaled', 'std_'+window+'_scaled', 'mean_'+window+'_scaled', 'maxmin_'+window+'_scaled']

    # we fit the data
    data[features_col] = scaler.fit_transform(data[features_col].values)

    return data, features_col+['weekend'], scaler

def generate_features(data: pd.DataFrame, column_name: Optional[str]='mains', window: Optional[str or List[str]]='1h', fillna_method :Optional[str]='bfill') -> Tuple[pd.DataFrame, List[str]]:
    """
    Generates features for classifications
    data: the DataFrame to use
    column_name: the name of the column with the power data
    windows: (optional) the window(s) of time for the rolling transformations
    fillna_method: (optional) the method to use the fill na values that will occure due to the rolling transformations
    returns: a DataFrame with the old and new features, a list containing the names of the new features columns, and the fitter scaler
    """
    # we prepare our features
    if not isinstance(window, list):
        window = [window]

    features_col = []
    for w in window:
        data['mean_'+w] = data[column_name].rolling(w, center=True).mean().values.reshape(-1,1)
        data['std_'+w] = data[column_name].rolling(w, center=True).std().values.reshape(-1,1)
        data['maxmin_'+w] = data[column_name].rolling(w, center=True).max().values.reshape(-1,1) - data[column_name].rolling(w, center=True).min().values.reshape(-1,1)
        data['peaks_'+w] = ((data[column_name] - data['mean_'+w]) < 1e-3).astype(int).rolling(w, center=True).sum().values.reshape(-1,1)

        # we generate a list of the column names generated
        features_col += ['std_'+w, 'mean_'+w, 'maxmin_'+w, 'peaks_'+w]

    data['weekend'] = data.index.day_of_week.isin([5, 6]).astype(int)
    features_col += ['weekend']
    
    # we remove the NA values
    data = data.fillna(method=fillna_method)


    return data, features_col

def plot_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, float]:
    """
    Calculates and plots the confusion matrix and prints the f_beta and accuracy scores
    y_true: the true values
    y_pred: the predictions
    returns: the f_beta and accuracy scores
    """
    f_beta = fbeta_score(y_true, y_pred, average="macro", beta=0.5)
    acc = accuracy_score(y_true, y_pred)
    print(f'Score f_beta : {f_beta:.3%}')
    print(f'Score accuracy : {acc:.3%}')
    ax = sns.heatmap(pd.crosstab(y_true, y_pred, normalize=True), annot=True, fmt='.2%', vmin=0, vmax=1, square=True, cmap=sns.cm.rocket_r);
    ax.set_title('Confusion Matrix')
    ax.set_xlabel('vérité');
    ax.set_ylabel('predictions');

    return f_beta, acc


def plot_scores_param(X_train: np.ndarray, X_test: np.ndarray, y_train: np.ndarray, y_test: np.ndarray,
                      estimator: Any, param_name: str, param_range: List[float], other_params: Optional[Dict[str, Any]]={}, recalculate_scores: Optional[bool]=True) -> Tuple[str, float, float]:
    """
    Performs a grid search on a model on a single parameter and displays the scores vs parameter
    X_train: the features to train the model on
    y_train: the labels to train the model
    X_test: the features to evaluate the model on
    y_test: the labels to evaluate the model
    estimator: the estimator to fit
    param_name: the name of the parameter on which we perform the grid search
    param_range: the range of the parameter to perform the grid search
    other_params: (optional) additional parameters to pass to the classifier
    recalculate_scores: (optional) whether or not we recalculate the score with the best parameters to plot a confusion matrix
    returns: the parameter name, its the best value, the accuracy and the fbeta score associated with the best value
    """
    f2_score = []
    score = []
    for p in param_range:
        classifier = estimator(**{param_name:p}, **other_params)
        classifier.fit(X_train, y_train)
        y_pred = classifier.predict(X_test)

        f2_score.append((fbeta_score(y_test, y_pred, average='macro', beta=0.5)))
        score.append(accuracy_score(y_test, y_pred))

        print(f"tested {param_name}={p} ...")

    best_param = np.argmax(f2_score)

    plt.figure(figsize=(10, 6));
    plt.plot(param_range, score, label='score', color='grey', linestyle='dashed');
    plt.plot(param_range, f2_score, label='fb score');
    plt.scatter(param_range[best_param], f2_score[best_param], label='fb max', marker='x', s=100, color='red')
    plt.legend();
    plt.title('fb and score = f({})'.format(param_name));
    plt.show();

    print('Meilleur fb score={:.2f} obtenu pour {}={:.2f}'.format(f2_score[best_param], param_name, param_range[best_param]))

    if recalculate_scores:
        classifier = estimator(**{param_name:param_range[best_param]})
        classifier.fit(X_train, y_train)
        y_pred = classifier.predict(X_test)

        plot_confusion_matrix(y_test, y_pred)

    return param_name, param_range[best_param], score[best_param], f2_score[best_param]
