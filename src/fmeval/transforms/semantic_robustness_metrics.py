import evaluate as hf_evaluate
from typing import List, Dict, Any

from fmeval.util import require
from fmeval.transforms.common import Mean
from fmeval.transforms.transform import Transform
from fmeval.transforms.util import validate_call


class BertScoreDissimilarity(Transform):
    """This Transform augments its input record with the BERTScore Dissimilarity metric.

    BERTScore Dissimilarity is simply 1 - BERTScore
    (https://huggingface.co/spaces/evaluate-metric/bertscore).
    This Transform uses the mean of a list of BERTScore values as the BERTScore
    in the formula above.
    """

    def __init__(self, bert_score_keys: List[str], output_key: str):
        """BertScoreDissimilarity initializer.

        :param bert_score_keys: The keys corresponding to the BERTScore values.
        :param output_key: The key corresponding to the output of this transform.
        """
        super().__init__(bert_score_keys, output_key)
        self.register_input_output_keys(bert_score_keys, [output_key])
        self.bert_score_keys = bert_score_keys
        self.output_key = output_key

    @validate_call
    def __call__(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Augment the input record with the computed BERTScore Dissimilarity metric.

        :param record: The input record.
        :returns: The input record with the BERTScore Dissimilarity metric added in.
        """
        add_mean_bert_score = Mean(
            self.bert_score_keys,
            self.output_key,
        )
        record = add_mean_bert_score(record)
        # Override the intermediate value corresponding to self.output_key
        # (i.e. the mean bert score) to 1 - mean.
        record[self.output_key] = 1 - record[self.output_key]
        return record


class WER(Transform):
    """This Transform computes the Word Error Rate metric and augments its input record with the computed value.

    Word Error Rate measures syntactic differences, that is, changes in the words, whereas BERTScore Dissimilarity
    measures semantic differences. Semantic differences account for cases when the precise words in the output
    change but the meaning is the same. For example, consider the outputs "it is pouring down today" vs.
    "it is very rainy today".
    """

    def __init__(self, prediction_keys: List[str], reference_keys: List[str], output_key: str):
        """WER initializer.

        Note that the order of elements in `prediction_keys` and `reference_keys` matters;
        the kth element of `prediction_keys` should correspond to the kth element of
        `reference_keys`.

        :param prediction_keys: The record keys corresponding to model predictions.
        :param reference_keys: The record keys corresponding ot reference, aka target, values.
        :param output_key: The output key to assign the computed WER value.
        """
        require(
            len(prediction_keys) == len(reference_keys),
            "prediction_keys and reference_keys should have the same number of elements. "
            f"prediction_keys has {len(prediction_keys)} elements while reference_keys has "
            f"{len(reference_keys)} elements.",
        )
        super().__init__(prediction_keys, reference_keys, output_key)
        self.register_input_output_keys(prediction_keys + reference_keys, [output_key], allow_duplicates=True)
        self.prediction_keys = prediction_keys
        self.reference_keys = reference_keys
        self.output_key = output_key
        self.wer = hf_evaluate.load("wer")

    @validate_call
    def __call__(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Augment the input record with the computed WER metric.

        :param record: The input record.
        :returns: The input record with the WER metric added in.
        """
        wer_metric = self.wer.compute(
            predictions=[record[prediction_key] for prediction_key in self.prediction_keys],
            references=[record[reference_key] for reference_key in self.reference_keys],
        )
        record[self.output_key] = wer_metric
        return record
