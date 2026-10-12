---
base_model: google/gemma-2b
library_name: transformers
license: gemma
pipeline_tag: text-generation
extra_gated_heading: Access Gemma on Hugging Face
extra_gated_prompt: To access Gemma on Hugging Face, you’re required to review and
  agree to Google’s usage license. To do this, please ensure you’re logged in to Hugging
  Face and click below. Requests are processed immediately.
extra_gated_button_content: Acknowledge license
---

# Gemma Model Card

**Model Page**: [Gemma](https://ai.google.dev/gemma/docs)

This model card corresponds to the 2B finetuned version of the Gemma-APS model.
You can also visit the model card of the [7B finetuned model](https://huggingface.co/google/gemma-7b-aps-it).

**Resources and Technical Documentation**:

* [Scalable and Domain-General Abstractive Proposition Segmentation](https://arxiv.org/abs/2406.19803)
* [Gemma Technical Report](https://storage.googleapis.com/deepmind-media/gemma/gemma-report.pdf)
* [Responsible Generative AI Toolkit](https://ai.google.dev/responsible)
* [Gemma on Kaggle](https://www.kaggle.com/models/google/gemma)

**Terms of Use**: [Terms](https://www.kaggle.com/models/google/gemma/license/consent/verify/huggingface?returnModelRepoId=google/gemma-2b-aps-it)

**Authors**: Mohammad Javad Hosseini, Yang Gao, Tim Baumgärtner, Alex Fabrikant, Reinald Kim Amplayo

## Model Information

Summary description and brief definition of inputs and outputs.

### Description

Gemma-APS is a generative model and a research tool for **abstractive proposition segmentation** (APS for short), a.k.a. claim extraction.
Given a text passage, the model segments the content into the individual facts, statements, and ideas expressed in the text, and restates
them in full sentences with small changes to the original text.

This model can be used for research where there is a need to break down text content into meaningful components. Applications include
grounding, retrieval, fact-checking, and evaluation of generation tasks (such as summarization) where it can be useful to divide up
individual propositions (claims) so that they can be processed independently. For more information, check out the [research paper](https://arxiv.org/abs/2406.19803).

### Context Length

Models are trained on a context length of 8192 tokens.

### Usage

Below we share some code snippets on how to get quickly started with running the model. First make sure to `pip install -U transformers nltk`,
then copy the snippet from the section that is relevant for your usecase.

For ease-of-use, we define two helper functions for pre-processing input and post-processing output of the model:

```py
import nltk
import re

nltk.download('punkt')

start_marker = '<s>'
end_marker = '</s>'
separator = '\n'

def create_propositions_input(text: str) -> str:
    input_sents = nltk.tokenize.sent_tokenize(text)
    propositions_input = ''
    for sent in input_sents:
        propositions_input += f'{start_marker} ' + sent + f' {end_marker}{separator}'
    propositions_input = propositions_input.strip(f'{separator}')
    return propositions_input

def process_propositions_output(text):
    pattern = re.compile(f'{re.escape(start_marker)}(.*?){re.escape(end_marker)}', re.DOTALL)
    output_grouped_strs = re.findall(pattern, text)
    predicted_grouped_propositions = []
    for grouped_str in output_grouped_strs:
        grouped_str = grouped_str.strip(separator)
        props = [x[2:] for x in grouped_str.split(separator)]
        predicted_grouped_propositions.append(props)
    return predicted_grouped_propositions
```

#### Usage with the `pipeline` API

```py
from transformers import pipeline
import torch

generator = pipeline('text-generation', 'google/gemma-2b-aps-it', device_map='auto', torch_dtype=torch.bfloat16)

passage = 'Sarah Stage, 30, welcomed James Hunter into the world on Tuesday.\nThe baby boy weighed eight pounds seven ounces and was 22 inches long.'
messages = [{'role': 'user', 'content': create_propositions_input(passage)}]
output = generator(messages, max_new_tokens=4096, return_full_text=False)
result = process_propositions_output(output[0]['generated_text'])
print(result)
```


<details>

<summary>Example output</summary>

```json
[
  [
    "Sarah Stage welcomed James Hunter into the world.",
    "Sarah Stage welcomed James Hunter on Tuesday.",
    "Sarah Stage is 30 years old."
  ],
  [
    "James Hunter weighed eight pounds seven ounces.",
    "James Hunter was 22 inches long."
  ]
]
```
</details>


#### Usage with `AutoModel` and `AutoTokenizer` APIs

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

model_id = 'google/gemma-2b-aps-it'
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    device_map='auto',
    torch_dtype=torch.bfloat16,
)

passage = "For more than 40 years, the lyrics of American Pie have been puzzled over. This week the handwritten lyrics sold for more than $1 million at auction. The verses contain hidden references to seminal events of the 50s and 60s. It includes nods to Buddy Holly, Charles Manson and Martin Luther King."
messages = [{'role': 'user', 'content': create_propositions_input(passage)}]
inputs = tokenizer.apply_chat_template(messages, return_tensors='pt', add_generation_prompt=True, return_dict=True).to(model.device)

output = model.generate(**inputs, max_new_tokens=4096, do_sample=False)
generated_text = tokenizer.batch_decode(output[:, inputs['input_ids'].shape[1]:], skip_special_tokens=True)[0]
result = process_propositions_output(generated_text)
print(result)
```

<details>

<summary>Example output</summary>

```json
[
  [
    "The lyrics of American Pie have been puzzled over.",
    "The lyrics of American Pie have been puzzled for more than 40 years."
  ],
  [
    "This week the handwritten lyrics sold for more than $1 million.",
    "This week the handwritten lyrics sold at auction."
  ],
  [
    "The verses contain hidden references to seminal events.",
    "The verses contain hidden references to events of the 50s.",
    "The verses contain hidden references to events of the 60s."
  ],
  [
    "The lyrics include nods to Buddy Holly.",
    "The lyrics include nods to Charles Manson.",
    "The lyrics include nods to Martin Luther King."
  ]
]
```

</details>


### Inputs and outputs

*   **Input:** A text passage.
*   **Output:** List of propositions for all the sentences in the text passage. The propositions for each sentence are grouped separately.


## Model Data

Data used for model training and how the data was processed.

### Training Dataset

* The training data contains synthetically generated examples, where each example has (input passage, propositions list) pairs, with the
  propositions list containing propositions for all the sentences in the input passage (one group of propositions for each sentence).
* The input passages are generated by few-shot prompting Gemini Ultra.
* The propositions list is generated by applying a teacher LLM on the input passage. The teacher LLM is a Gemini Pro model trained on
  a filtered version of the ROSE dataset.

See the [research paper](https://arxiv.org/abs/2406.19803) for all the details.

### Data Preprocessing

* We filtered example passages that have >=4 tokens overlap with any of the few-shot examples used for prompting Gemini Ultra.
* We used the ROSE dataset for training the teacher LLM (Gemini Pro). We filtered ROSE examples using an entailment model to remove
  cases that do not satisfy desired properties of propositions.


## Implementation Information

Details about the model internals.

### Hardware

Similar to Gemma, Gemma-APS was trained on [TPUv5e](https://cloud.google.com/tpu/docs/intro-to-tpu?_gl=1*18wi411*_ga*MzE3NDU5OTY1LjE2MzQwNDA4NDY.*_ga_WH2QY8WWF5*MTcxMTA0MjUxMy4xNy4wLjE3MTEwNDI1MTkuMC4wLjA.&_ga=2.239449409.-317459965.1634040846).

Training large language models requires significant computational power. TPUs, designed specifically for matrix operations common in machine learning, offer several advantages in this domain:

Performance: TPUs are specifically designed to handle the massive computations involved in training LLMs. They can speed up training considerably compared to CPUs.
Memory: TPUs often come with large amounts of high-bandwidth memory, allowing for the handling of large models and batch sizes during training. This can lead to better model quality.
Scalability: TPU Pods (large clusters of TPUs) provide a scalable solution for handling the growing complexity of large foundation models. You can distribute training across multiple TPU devices for faster and more efficient processing.
Cost-effectiveness: In many scenarios, TPUs can provide a more cost-effective solution for training large models compared to CPU-based infrastructure, especially when considering the time and resources saved due to faster training.
These advantages are aligned with [Google's commitments to operate sustainably](https://sustainability.google/operating-sustainably/).

### Software

Training was done using [JAX](https://github.com/jax-ml/jax).

JAX allows researchers to leverage the latest generation of hardware, including TPUs, for faster and more efficient training of large models.


## Evaluation

Model evaluation metrics and results.

### Benchmark Results

Evaluation was done on one existing in-domain dataset (development set of the [ROSE](https://github.com/Yale-LILY/ROSE) dataset filtered by an entailment model) and two out-of-domain datasets introduced in the paper. Evaluation was performed based on our new metrics for the abstractive proposition segmentation task.


## Ethics and Safety

Ethics and safety evaluation approach and results.

### Evaluation Approach

These models are only suitable for abstractive proposition segmentation for English text, not any other task or language. While we have tested the models on three evaluation datasets and have obtained positive results compared to strong baselines, the model might still have errors on some examples.


## Usage and Limitations

These models have certain limitations that users should be aware of.

### Intended Usage

These models are only suitable for abstractive proposition segmentation for English text, not any other task or language.
While we have tested it on three evaluation datasets and have obtained positive results compared to strong baselines,
the models might still have errors on some examples.

### Limitations

These models have certain limitations that users should be aware of.

* Training Data
  * The quality and diversity of the training data significantly influence the
    model's capabilities. Biases or gaps in the training data can lead to
    limitations in the model's responses.
  * The scope of the training dataset determines the subject areas the model can
    handle effectively.
  * We have tested our models on passages from different domains, where passages
    contain a few sentences. 
  * This model supports abstractive proposition segmentation in English, not any
    other language.
* Language Ambiguity and Nuance
  * Natural language is inherently complex. LLMs might struggle to grasp subtle
    nuances, sarcasm, or figurative language.
* Factual Accuracy
  * LLMs generate responses based on information they learned from their
    training datasets, but they are not knowledge bases. They may generate
    incorrect or outdated factual statements.
* Common Sense
  * LLMs rely on statistical patterns in language. They might lack the ability
    to apply common sense reasoning in certain situations.

### Ethical Considerations and Risks

The development of large language models (LLMs) raises several ethical concerns.
In creating an open model, we have carefully considered the following:

* Bias and Fairness
  * LLMs trained on large-scale, real-world text data can reflect socio-cultural
    biases embedded in the training material. These models underwent careful
    scrutiny, input data pre-processing described and posterior evaluations
    reported in this card.
* Misinformation and Misuse
  * LLMs can be misused to generate text that is false, misleading, or harmful.
  * Guidelines are provided for responsible use with the model, see the
    [Responsible Generative AI Toolkit](http://ai.google.dev/gemma/responsible).
* Transparency and Accountability:
  * This model card summarizes details on the models' architecture,
    capabilities, limitations, and evaluation processes.
  * A responsibly developed open model offers the opportunity to share
    innovation by making LLM technology accessible to developers and researchers
    across the AI ecosystem.

Risks identified and mitigations:

* Perpetuation of biases: It's encouraged to perform continuous monitoring
  (using evaluation metrics, human review) and the exploration of de-biasing
  techniques during model training, fine-tuning, and other use cases.
* Generation of harmful content: Mechanisms and guidelines for content safety
  are essential. Developers are encouraged to exercise caution and implement
  appropriate content safety safeguards based on their specific product policies
  and application use cases.
* Misuse for malicious purposes: Technical limitations and developer and
  end-user education can help mitigate against malicious applications of LLMs.
  Educational resources and reporting mechanisms for users to flag misuse are
  provided. Prohibited uses of Gemma models are outlined in the
  [Gemma Prohibited Use Policy](https://ai.google.dev/gemma/prohibited_use_policy).
* Privacy violations: Models were trained on data filtered for removal of PII
  (Personally Identifiable Information). Developers are encouraged to adhere to
  privacy regulations with privacy-preserving techniques.

### Benefits

These models are useful for academics working on abstractive proposition segmentation (claim extraction) research or other problems (e.g., grounding, retrieval, fact-checking) that could benefit from this task.
