import re
from typing import NamedTuple, List, Optional, Tuple
from unittest.mock import patch, MagicMock

import pytest
import ray
from _pytest.fixtures import fixture
from ray.data import Dataset

from fmeval.constants import (
    DatasetColumns,
    MIME_TYPE_JSON,
)
from fmeval.data_loaders.data_config import DataConfig
from fmeval.eval_algorithms import (
    EvalScore,
    EvalOutput,
    CategoryScore,
    BUILT_IN_DATASET_DEFAULT_PROMPT_TEMPLATES,
    DEFAULT_PROMPT_TEMPLATE,
    WOMENS_CLOTHING_ECOMMERCE_REVIEWS,
)
from fmeval.eval_algorithms.classification_accuracy_semantic_robustness import (
    ClassificationAccuracySemanticRobustnessConfig,
    ClassificationAccuracySemanticRobustness,
    RANDOM_UPPERCASE,
    ADD_REMOVE_WHITESPACE,
    BUTTER_FINGER,
    DELTA_CLASSIFICATION_ACCURACY_SCORE,
)
from fmeval.eval_algorithms.classification_accuracy import CLASSIFICATION_ACCURACY_SCORE
from fmeval.exceptions import EvalAlgorithmClientError
from fmeval.model_runners.model_runner import ModelRunner

DATASET = ray.data.from_items(
    [
        {
            DatasetColumns.MODEL_INPUT.value.name: "Delicious cake! Would buy again.",
            DatasetColumns.TARGET_OUTPUT.value.name: "4",
            DatasetColumns.MODEL_OUTPUT.value.name: "Some model output.",
            DatasetColumns.CATEGORY.value.name: "brownie",
        },
        {
            DatasetColumns.MODEL_INPUT.value.name: "Tasty cake! Must eat.",
            DatasetColumns.TARGET_OUTPUT.value.name: "4",
            DatasetColumns.MODEL_OUTPUT.value.name: "Some model output.",
            DatasetColumns.CATEGORY.value.name: "vanilla cake",
        },
        {
            DatasetColumns.MODEL_INPUT.value.name: "Terrible! Nightmarish cake.",
            DatasetColumns.TARGET_OUTPUT.value.name: "1",
            DatasetColumns.MODEL_OUTPUT.value.name: "Some model output.",
            DatasetColumns.CATEGORY.value.name: "vanilla cake",
        },
    ]
)

DATASET_WITHOUT_CATEGORY = DATASET.drop_columns(cols=[DatasetColumns.CATEGORY.value.name])

DATASET_WITHOUT_MODEL_OUTPUT = DATASET.drop_columns(cols=[DatasetColumns.MODEL_OUTPUT.value.name])

DATASET_WITHOUT_MODEL_INPUT = DATASET.drop_columns(cols=[DatasetColumns.MODEL_INPUT.value.name])


CATEGORY_SCORES = [
    CategoryScore(
        name="brownie",
        scores=[
            EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=0.0),
            EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=0.0),
        ],
    ),
    CategoryScore(
        name="vanilla cake",
        scores=[
            EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=0.0),
            EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=0.0),
        ],
    ),
]


class ConstantModel(ModelRunner):
    def __init__(self):
        super().__init__('{"data": $prompt}', output="output")

    def predict(self, prompt: str) -> Tuple[Optional[str], Optional[float]]:
        return "Some model output.", None


class TestClassificationAccuracySemanticRobustness:
    @fixture(scope="module")
    def config(self) -> ClassificationAccuracySemanticRobustnessConfig:
        return ClassificationAccuracySemanticRobustnessConfig(
            valid_labels=["1", "2", "3", "4", "5"], num_perturbations=2
        )

    class TestCaseClassificationAccuracySemanticRobustnessInvalidConfig(NamedTuple):
        valid_labels: List[str]
        perturbation_type: str
        expected_error_message: str

    @pytest.mark.parametrize(
        "test_case",
        [
            TestCaseClassificationAccuracySemanticRobustnessInvalidConfig(
                valid_labels=["1", "2"],
                perturbation_type="my_perturb",
                expected_error_message="Invalid perturbation type 'my_perturb requested, please choose from "
                "acceptable values: dict_keys(['butter_finger', 'random_uppercase', 'add_remove_whitespace'])",
            ),
        ],
    )
    def test_classification_accuracy_semantic_robustness_invalid_config(self, test_case):
        """
        GIVEN invalid configs
        WHEN ClassificationAccuracySemanticRobustnessConfig is initialized
        THEN correct exception with proper message is raised
        """
        with pytest.raises(EvalAlgorithmClientError, match=re.escape(test_case.expected_error_message)):
            ClassificationAccuracySemanticRobustnessConfig(
                valid_labels=test_case.valid_labels,
                perturbation_type=test_case.perturbation_type,
            )

    def test_classification_accuracy_config_format_with_castable_labels(self):
        """
        GIVEN valid labels are int but can be cast to str
        WHEN ClassificationAccuracySemanticRobustnessConfig is initialized with castable integer labels
        THEN warning is raised, ClassificationAccuracySemanticRobustnessConfig is initialized successfully
        """
        with pytest.warns():
            castable_config = ClassificationAccuracySemanticRobustnessConfig(
                valid_labels=[1, 2, 3, 4, 5], perturbation_type="butter_finger"
            )
            assert castable_config.valid_labels == ["1", "2", "3", "4", "5"]

    class TestCaseClassificationAccuracySemanticRobustnessEvaluateSample(NamedTuple):
        model_input: str
        original_model_output: str
        perturbed_model_output_1: str
        perturbed_model_output_2: str
        target_output: str
        expected_response: List[EvalScore]
        config: ClassificationAccuracySemanticRobustnessConfig

    @pytest.mark.parametrize(
        "test_case",
        [
            TestCaseClassificationAccuracySemanticRobustnessEvaluateSample(
                model_input="Ok brownie.",
                original_model_output="3",
                perturbed_model_output_1="Some model output.",
                perturbed_model_output_2="Some model output.",
                target_output="3",
                expected_response=[
                    EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=1.0),
                    EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=1.0),
                ],
                config=ClassificationAccuracySemanticRobustnessConfig(
                    valid_labels=["1", "2", "3", "4", "5"],
                    num_perturbations=2,
                ),
            ),
            TestCaseClassificationAccuracySemanticRobustnessEvaluateSample(
                model_input="Good cake.",
                original_model_output="4",
                perturbed_model_output_1="Another model output.",
                perturbed_model_output_2="Some model output.",
                target_output="4",
                expected_response=[
                    EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=1.0),
                    EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=1.0),
                ],
                config=ClassificationAccuracySemanticRobustnessConfig(
                    valid_labels=["1", "2", "3", "4", "5"], num_perturbations=2, perturbation_type=BUTTER_FINGER
                ),
            ),
            TestCaseClassificationAccuracySemanticRobustnessEvaluateSample(
                model_input="Delicious! Nightmarish cake.",
                original_model_output="5",
                perturbed_model_output_1="Another model output.",
                perturbed_model_output_2="Some model output.",
                target_output="2",
                expected_response=[
                    EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=0.0),
                    EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=0.0),
                ],
                config=ClassificationAccuracySemanticRobustnessConfig(
                    valid_labels=["1", "2", "3", "4", "5"], num_perturbations=2, perturbation_type=RANDOM_UPPERCASE
                ),
            ),
            TestCaseClassificationAccuracySemanticRobustnessEvaluateSample(
                model_input="Terrible! Nightmarish cake.",
                original_model_output="1",
                perturbed_model_output_1="Another model output.",
                perturbed_model_output_2="Another model output.",
                target_output="1",
                expected_response=[
                    EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=1.0),
                    EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=1.0),
                ],
                config=ClassificationAccuracySemanticRobustnessConfig(
                    valid_labels=["1", "2", "3", "4", "5"], num_perturbations=2, perturbation_type=ADD_REMOVE_WHITESPACE
                ),
            ),
        ],
    )
    def test_classification_accuracy_semantic_robustness_evaluate_sample(self, test_case):
        """
        GIVEN valid inputs
        WHEN ClassificationAccuracySemanticRobustness.evaluate_sample is called
        THEN correct List of EvalScores is returned
        """
        model = MagicMock()
        model.predict.side_effect = [
            (test_case.original_model_output,),
            (test_case.perturbed_model_output_1,),
            (test_case.perturbed_model_output_2,),
        ]

        eval_algorithm = ClassificationAccuracySemanticRobustness(test_case.config)
        assert (
            eval_algorithm.evaluate_sample(
                model_input=test_case.model_input, model=model, target_output=test_case.target_output
            )
            == test_case.expected_response
        )
        assert model.predict.call_count == 3

    @pytest.mark.parametrize(
        "test_case",
        [
            TestCaseClassificationAccuracySemanticRobustnessEvaluateSample(
                model_input="Ok brownie.",
                original_model_output="3",
                perturbed_model_output_1="Some model output.",
                perturbed_model_output_2="Some model output.",
                target_output="3",
                expected_response=[
                    EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=1.0),
                    EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=1.0),
                ],
                config=ClassificationAccuracySemanticRobustnessConfig(
                    valid_labels=["1", "2", "3", "4", "5"],
                    num_perturbations=2,
                ),
            )
        ],
    )
    def test_classification_accuracy_semantic_robustness_evaluate_sample_with_model_output(self, test_case):
        """
        GIVEN valid inputs with model_output
        WHEN ClassificationAccuracySemanticRobustness.evaluate_sample is called
        THEN correct List of EvalScores is returned
        """
        model = MagicMock()
        model.predict.side_effect = [
            (test_case.perturbed_model_output_1,),
            (test_case.perturbed_model_output_2,),
        ]

        eval_algorithm = ClassificationAccuracySemanticRobustness(test_case.config)
        assert (
            eval_algorithm.evaluate_sample(
                model_input=test_case.model_input,
                model=model,
                model_output=test_case.original_model_output,
                target_output=test_case.target_output,
            )
            == test_case.expected_response
        )
        assert model.predict.call_count == 2

    class TestCaseClassificationAccuracySemanticRobustnessEvaluate(NamedTuple):
        input_dataset: Dataset
        input_dataset_with_generated_model_output: Dataset
        prompt_template: Optional[str]
        dataset_config: Optional[DataConfig]
        expected_response: List[EvalOutput]
        save_data: bool

    @pytest.mark.parametrize(
        "test_case",
        [
            # Built-in datasets evaluate for dataset without category
            TestCaseClassificationAccuracySemanticRobustnessEvaluate(
                input_dataset=DATASET_WITHOUT_MODEL_OUTPUT.drop_columns(cols=DatasetColumns.CATEGORY.value.name),
                input_dataset_with_generated_model_output=DATASET_WITHOUT_CATEGORY,
                dataset_config=None,
                prompt_template=None,
                save_data=True,
                expected_response=[
                    EvalOutput(
                        eval_name="classification_accuracy_semantic_robustness",
                        dataset_name=WOMENS_CLOTHING_ECOMMERCE_REVIEWS,
                        dataset_scores=[
                            EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=0.0),
                            EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=0.0),
                        ],
                        prompt_template=BUILT_IN_DATASET_DEFAULT_PROMPT_TEMPLATES[WOMENS_CLOTHING_ECOMMERCE_REVIEWS],
                        category_scores=None,
                        output_path="/tmp/eval_results/classification_accuracy_semantic_robustness_womens_clothing_ecommerce_reviews.jsonl",
                    ),
                ],
            ),
            # Built-in datasets evaluate for dataset with category
            TestCaseClassificationAccuracySemanticRobustnessEvaluate(
                input_dataset=DATASET_WITHOUT_MODEL_OUTPUT,
                input_dataset_with_generated_model_output=DATASET,
                dataset_config=None,
                prompt_template=None,
                save_data=True,
                expected_response=[
                    EvalOutput(
                        eval_name="classification_accuracy_semantic_robustness",
                        dataset_name=WOMENS_CLOTHING_ECOMMERCE_REVIEWS,
                        dataset_scores=[
                            EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=0.0),
                            EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=0.0),
                        ],
                        prompt_template=BUILT_IN_DATASET_DEFAULT_PROMPT_TEMPLATES[WOMENS_CLOTHING_ECOMMERCE_REVIEWS],
                        category_scores=CATEGORY_SCORES,
                        output_path="/tmp/eval_results/classification_accuracy_semantic_robustness_womens_clothing_ecommerce_reviews.jsonl",
                    ),
                ],
            ),
            # Custom dataset evaluate, with input prompt template
            TestCaseClassificationAccuracySemanticRobustnessEvaluate(
                input_dataset=DATASET_WITHOUT_MODEL_OUTPUT.drop_columns(cols=DatasetColumns.CATEGORY.value.name),
                input_dataset_with_generated_model_output=DATASET_WITHOUT_CATEGORY,
                dataset_config=DataConfig(
                    dataset_name="my_custom_dataset",
                    dataset_uri="tba",
                    dataset_mime_type=MIME_TYPE_JSON,
                    model_input_location="tba",
                    target_output_location="tba",
                    model_output_location=None,
                    category_location="tba",
                ),
                prompt_template="$model_input",
                save_data=False,
                expected_response=[
                    EvalOutput(
                        eval_name="classification_accuracy_semantic_robustness",
                        dataset_name="my_custom_dataset",
                        dataset_scores=[
                            EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=0.0),
                            EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=0.0),
                        ],
                        prompt_template="$model_input",
                        category_scores=None,
                        output_path="/tmp/eval_results/classification_accuracy_semantic_robustness_my_custom_dataset.jsonl",
                    ),
                ],
            ),
            # Custom dataset evaluate, without input prompt template
            TestCaseClassificationAccuracySemanticRobustnessEvaluate(
                input_dataset=DATASET_WITHOUT_MODEL_OUTPUT.drop_columns(cols=DatasetColumns.CATEGORY.value.name),
                input_dataset_with_generated_model_output=DATASET_WITHOUT_CATEGORY,
                dataset_config=DataConfig(
                    dataset_name="my_custom_dataset",
                    dataset_uri="tba",
                    dataset_mime_type=MIME_TYPE_JSON,
                    model_input_location="tba",
                    target_output_location="tba",
                    model_output_location=None,
                    category_location="tba",
                ),
                prompt_template=None,
                save_data=False,
                expected_response=[
                    EvalOutput(
                        eval_name="classification_accuracy_semantic_robustness",
                        dataset_name="my_custom_dataset",
                        dataset_scores=[
                            EvalScore(name=CLASSIFICATION_ACCURACY_SCORE, value=0.0),
                            EvalScore(name=DELTA_CLASSIFICATION_ACCURACY_SCORE, value=0.0),
                        ],
                        prompt_template=DEFAULT_PROMPT_TEMPLATE,
                        category_scores=None,
                        output_path="/tmp/eval_results/classification_accuracy_semantic_robustness_my_custom_dataset.jsonl",
                    ),
                ],
            ),
        ],
    )
    @patch("fmeval.eval_algorithms.classification_accuracy_semantic_robustness.get_dataset")
    @patch("fmeval.eval_algorithms.classification_accuracy_semantic_robustness.save_dataset")
    @patch(
        "fmeval.eval_algorithms.classification_accuracy_semantic_robustness.generate_model_predict_response_for_dataset"
    )
    @patch("fmeval.eval_algorithms.classification_accuracy_semantic_robustness.ClassificationAccuracy")
    def test_classification_accuracy_semantic_robustness_evaluate(
        self,
        classification_accuracy,
        generate_model_predict_response_for_dataset,
        save_dataset,
        get_dataset,
        test_case,
        config,
    ):
        """
        GIVEN valid inputs i.e. input data config for a dataset without model_outputs, an input ModelRunner
            and request to save records with scores
        WHEN ClassificationAccuracySemanticRobustness evaluate() method is called
        THEN correct EvalOutput is returned
        """
        get_dataset.return_value = test_case.input_dataset
        generate_model_predict_response_for_dataset.return_value = test_case.input_dataset_with_generated_model_output
        classification_accuracy.return_value = MagicMock()

        eval_algorithm = ClassificationAccuracySemanticRobustness()
        actual_response = eval_algorithm.evaluate(
            model=ConstantModel(),
            dataset_config=test_case.dataset_config,
            save=test_case.save_data,
            prompt_template=test_case.prompt_template,
        )
        assert save_dataset.called == test_case.save_data
        assert actual_response == test_case.expected_response

    class TestCaseClassificationAccuracySemanticRobustnessEvaluateInvalid(NamedTuple):
        input_dataset: Dataset
        dataset_config: Optional[DataConfig]
        prompt_template: Optional[str]
        model_provided: bool
        expected_error_message: str

    @pytest.mark.parametrize(
        "test_case",
        [
            TestCaseClassificationAccuracySemanticRobustnessEvaluateInvalid(
                input_dataset=DATASET_WITHOUT_CATEGORY,
                dataset_config=None,
                prompt_template=None,
                model_provided=False,
                expected_error_message="Missing required input: model i.e. ModelRunner, for ClassificationAccuracySemanticRobustness "
                "evaluate",
            ),
            TestCaseClassificationAccuracySemanticRobustnessEvaluateInvalid(
                input_dataset=DATASET_WITHOUT_CATEGORY.drop_columns(cols=[DatasetColumns.MODEL_INPUT.value.name]),
                dataset_config=DataConfig(
                    dataset_name="my_custom_dataset",
                    dataset_uri="tba",
                    dataset_mime_type=MIME_TYPE_JSON,
                    model_input_location="tba",
                    target_output_location="tba",
                    model_output_location=None,
                    category_location="tba",
                ),
                prompt_template=None,
                model_provided=True,
                expected_error_message="Missing required column: model_input, for evaluate",
            ),
            TestCaseClassificationAccuracySemanticRobustnessEvaluateInvalid(
                input_dataset=DATASET_WITHOUT_CATEGORY.drop_columns(cols=[DatasetColumns.TARGET_OUTPUT.value.name]),
                dataset_config=DataConfig(
                    dataset_name="my_custom_dataset",
                    dataset_uri="tba",
                    dataset_mime_type=MIME_TYPE_JSON,
                    model_input_location="tba",
                    target_output_location="tba",
                    model_output_location=None,
                    category_location="tba",
                ),
                prompt_template=None,
                model_provided=True,
                expected_error_message="Missing required column: target_output, for evaluate",
            ),
        ],
    )
    @patch("fmeval.model_runners.model_runner.ModelRunner")
    @patch("fmeval.eval_algorithms.classification_accuracy_semantic_robustness.get_dataset")
    @patch("fmeval.eval_algorithms.classification_accuracy_semantic_robustness.ClassificationAccuracy")
    def test_classification_accuracy_semantic_robustness_evaluate_invalid_input(
        self,
        classification_accuracy,
        get_dataset,
        model,
        test_case,
        config,
    ):
        """
        GIVEN invalid inputs
        WHEN ClassificationAccuracySemanticRobustness evaluate is called
        THEN correct exception with proper message is raised
        """
        classification_accuracy.return_value = MagicMock()
        eval_algorithm = ClassificationAccuracySemanticRobustness(config)
        get_dataset.return_value = test_case.input_dataset
        if not test_case.model_provided:
            model = None
        with pytest.raises(EvalAlgorithmClientError, match=re.escape(test_case.expected_error_message)):
            eval_algorithm.evaluate(
                model=model, dataset_config=test_case.dataset_config, prompt_template=test_case.prompt_template
            )
