import inspect
from collections import OrderedDict

import pandas as pd
from sklearn.model_selection import train_test_split

from .components import Estimator, handle_component
from .pipeline_plots import PipelinePlots

from evalml.objectives import get_objective
from evalml.utils import Logger


class PipelineBase:

    # Necessary for "Plotting" documentation, since Sphinx does not work well with instance attributes.
    plot = PipelinePlots

    def __init__(self, objective, component_list, n_jobs, random_state, **kwargs):
        """Machine learning pipeline made out of transformers and a estimator.

        Arguments:
            objective (Object): the objective to optimize

            component_list (list): List of components in order

            random_state (int): random seed/state

            n_jobs (int): Number of jobs to run in parallel
        """

        self.objective = get_objective(objective)
        self.random_state = random_state
        self.component_list = [handle_component(component) for component in component_list]
        self.component_names = [comp.name for comp in self.component_list]
        self.input_feature_names = {}

        # check if one and only estimator in pipeline is the last element in component_list
        if not isinstance(self.component_list[-1], Estimator):
            raise ValueError("A pipeline must have an Estimator as the last component in component_list.")

        self.estimator = self.component_list[-1]
        self.problem_types = self.estimator.problem_types
        self.model_type = self.estimator.model_type

        self.name = self._generate_name()  # autogenerated
        self.results = {}
        self.n_jobs = n_jobs
        self.parameters = {}
        self._instantiate_components(kwargs)
        for component in self.component_list:
            self.parameters.update(component.parameters)

        self.plot = PipelinePlots(self)
        self.logger = Logger()

    def _instantiate_components(self, kwargs):
        for component in self.component_list:
            args = inspect.signature(component.__init__).parameters
            kwargs['n_jobs'] = self.n_jobs
            kwargs['random_state'] = self.random_state
            relevant_args = {}
            for k, v in kwargs.items():
                if k in args:
                    relevant_args[k] = v
            try:
                component = component.__class__(**relevant_args)
            except Exception as e:
                print("Error received when instantiating component {} with the following arguments {}".format(component, relevant_args))
                raise e

    def __getitem__(self, index):
        if isinstance(index, slice):
            raise NotImplementedError('Slicing pipelines is currently not supported.')
        elif isinstance(index, int):
            return self.component_list[index]
        else:
            return self.get_component(index)

    def __setitem__(self, index, value):
        raise NotImplementedError('Setting pipeline components is not supported.')

    def _generate_name(self):
        name = "{}".format(self.estimator.name)
        for index, component in enumerate(self.component_list[:-1]):
            if index == 0:
                name += " w/ {}".format(component.name)
            else:
                name += " + {}".format(component.name)
        return name

    def get_component(self, name):
        """Returns component by name

        Arguments:
            name (str): name of component

        Returns:
            Component: component to return

        """
        return next((component for component in self.component_list if component.name == name), None)

    def describe(self, return_dict=False):
        """Outputs pipeline details including component parameters

        Arguments:
            return_dict (bool): If True, return dictionary of information about pipeline. Defaults to false

        Returns:
            dict: dictionary of all component parameters if return_dict is True, else None
        """
        self.logger.log_title(self.name)
        self.logger.log("Problem Types: {}".format(', '.join([str(problem_type) for problem_type in self.problem_types])))
        self.logger.log("Model Type: {}".format(str(self.model_type)))
        better_string = "lower is better"
        if self.objective.greater_is_better:
            better_string = "greater is better"
        objective_string = "Objective to Optimize: {} ({})".format(self.objective.name, better_string)
        self.logger.log(objective_string)

        if self.estimator.name in self.input_feature_names:
            self.logger.log("Number of features: {}".format(len(self.input_feature_names[self.estimator.name])))

        # Summary of steps
        self.logger.log_subtitle("Pipeline Steps")
        for number, component in enumerate(self.component_list, 1):
            component_string = str(number) + ". " + component.name
            self.logger.log(component_string)
            component.describe(print_name=False)

        if return_dict:
            return self.parameters

    def _transform(self, X):
        X_t = X
        for component in self.component_list[:-1]:
            X_t = component.transform(X_t)
        return X_t

    def _fit(self, X, y):
        X_t = X
        y_t = y
        for component in self.component_list[:-1]:
            self.input_feature_names.update({component.name: list(pd.DataFrame(X_t))})
            if component._needs_fitting:
                X_t = component.fit_transform(X_t, y_t)
            else:
                X_t = component.transform(X_t, y_t)
        self.input_feature_names.update({self.estimator.name: list(pd.DataFrame(X_t))})
        self.estimator.fit(X_t, y_t)

    def fit(self, X, y, objective_fit_size=.2):
        """Build a model

        Arguments:
            X (pd.DataFrame or np.array): the input training data of shape [n_samples, n_features]

            y (pd.Series): the target training labels of length [n_samples]

            feature_types (list, optional): list of feature types. either numeric of categorical.
                categorical features will automatically be encoded

        Returns:

            self

        """
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        if not isinstance(y, pd.Series):
            y = pd.Series(y)

        if self.objective.needs_fitting:
            X, X_objective, y, y_objective = train_test_split(X, y, test_size=objective_fit_size, random_state=self.random_state)

        self._fit(X, y)

        if self.objective.needs_fitting:
            if self.objective.fit_needs_proba:
                y_predicted = self.predict_proba(X_objective)
            else:
                y_predicted = self.predict(X_objective)

            if self.objective.uses_extra_columns:
                self.objective.fit(y_predicted, y_objective, X_objective)
            else:
                self.objective.fit(y_predicted, y_objective)
        return self

    def predict(self, X):
        """Make predictions using selected features.

        Args:
            X (pd.DataFrame or np.array) : data of shape [n_samples, n_features]

        Returns:
            pd.Series : estimated labels
        """
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        X_t = self._transform(X)

        if self.objective and self.objective.needs_fitting:
            if self.objective.fit_needs_proba:
                y_predicted = self.predict_proba(X)
            else:
                X_t = self._transform(X)
                y_predicted = self.estimator.predict(X_t)

            if self.objective.uses_extra_columns:
                return self.objective.predict(y_predicted, X)

            return self.objective.predict(y_predicted)

        return self.estimator.predict(X_t)

    def predict_proba(self, X):
        """Make probability estimates for labels.

        Args:
            X (pd.DataFrame or np.array) : data of shape [n_samples, n_features]

        Returns:
            pd.DataFrame : probability estimates
        """
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        X = self._transform(X)
        proba = self.estimator.predict_proba(X)

        if proba.shape[1] <= 2:
            return proba[:, 1]
        else:
            return proba

    def score(self, X, y, other_objectives=None):
        """Evaluate model performance on current and additional objectives

        Args:
            X (pd.DataFrame or np.array) : data of shape [n_samples, n_features]
            y (pd.Series) : true labels of length [n_samples]
            other_objectives (list): list of other objectives to score

        Returns:
            float, dict:  score, ordered dictionary of other objective scores
        """
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        if not isinstance(y, pd.Series):
            y = pd.Series(y)

        other_objectives = other_objectives or []
        other_objectives = [get_objective(o) for o in other_objectives]
        y_predicted = None
        y_predicted_proba = None

        scores = []
        for objective in [self.objective] + other_objectives:
            if objective.score_needs_proba:
                if y_predicted_proba is None:
                    y_predicted_proba = self.predict_proba(X)
                y_predictions = y_predicted_proba
            else:
                if y_predicted is None:
                    y_predicted = self.predict(X)
                y_predictions = y_predicted

            if objective.uses_extra_columns:
                scores.append(objective.score(y_predictions, y, X))
            else:
                scores.append(objective.score(y_predictions, y))
        if not other_objectives:
            return scores[0], {}

        other_scores = OrderedDict(zip([n.name for n in other_objectives], scores[1:]))

        return scores[0], other_scores

    @property
    def feature_importances(self):
        """Return feature importances. Feature dropped by feaure selection are excluded"""
        feature_names = self.input_feature_names[self.estimator.name]
        importances = list(zip(feature_names, self.estimator.feature_importances))  # note: this only works for binary
        importances.sort(key=lambda x: -abs(x[1]))
        df = pd.DataFrame(importances, columns=["feature", "importance"])
        return df

    @classmethod
    def generate_name(self, component_list):
        """Returns name of pipeline generated through `component_list`

        Arguments:
            component_list(list[ComponentBase or str]): list of components

        Returns:
            name, str

        """
        component_list = [handle_component(component) for component in component_list]
        estimator = component_list[-1]
        name = "{}".format(estimator.name)
        for index, component in enumerate(component_list[:-1]):
            if index == 0:
                name += " w/ {}".format(component.name)
            else:
                name += " + {}".format(component.name)
        return name

    @classmethod
    def generate_model_type(self, component_list):
        component_list = [handle_component(component) for component in component_list]
        estimator = component_list[-1]
        return estimator.model_type
