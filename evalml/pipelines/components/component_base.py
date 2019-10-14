from evalml.utils import Logger


class ComponentBase:
    def __init__(self, name, component_type, parameters={}, needs_fitting=False, component_obj=None, random_state=0):
        self.name = name
        self.component_type = component_type
        self.random_state = random_state
        self._needs_fitting = needs_fitting
        self._component_obj = component_obj
        self.parameters = parameters
        self.logger = Logger()

    def fit(self, X, y):
        """Build a model

        Arguments:
            X (pd.DataFrame or np.array): the input training data of shape [n_samples, n_features]
            y (pd.Series): the target training labels of length [n_samples]

        Returns:
            self
        """
        try:
            return self._component_obj.fit(X, y)
        except AttributeError:
            raise RuntimeError("Component requires a fit method or a component_obj that implements fit")

    def describe(self, return_dict=False):
        """Describe a component and its parameters
        """
        title = self.name
        self.logger.log_subtitle(title)
        print("-" * len(title))
        for parameter in self.parameters:
            print("* ", parameter, ":", self.parameters[parameter])
        print("\n")
        if return_dict:
            return self.parameters
