import pandas as pd
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as SkLDA

from evalml.pipelines.components.transformers import Transformer
from evalml.utils.gen_utils import is_all_numeric


class LDA(Transformer):
    """Reduces the number of features by using Linear Discriminant Analysis"""
    name = 'Linear Discriminant Analysis Transformer'

    def __init__(self, n_components=None, random_state=0, **kwargs):
        """Initalizes an transformer that reduces the number of features using linear discriminant analysis."

        Arguments:
            n_components (int): the number of features to maintain after computationn. Defaults to None.
        """
        parameters = {"n_components": n_components}
        parameters.update(kwargs)
        lda = SkLDA(n_components=n_components, **kwargs)
        super().__init__(parameters=parameters,
                         component_obj=lda,
                         random_state=random_state)

    def fit(self, X, y):
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        if not is_all_numeric(X):
            raise ValueError("LDA input must be all numeric")

        self._component_obj.fit(X, y)
        return self

    def transform(self, X, y=None):
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        if not is_all_numeric(X):
            raise ValueError("LDA input must be all numeric")

        X_t = self._component_obj.transform(X)
        return pd.DataFrame(X_t, index=X.index, columns=[f"component_{i}" for i in range(X_t.shape[1])])

    def fit_transform(self, X, y=None):
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        if not is_all_numeric(X):
            raise ValueError("LDA input must be all numeric")

        X_t = self._component_obj.fit_transform(X, y)
        return pd.DataFrame(X_t, index=X.index, columns=[f"component_{i}" for i in range(X_t.shape[1])])
