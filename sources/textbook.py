"""
Transform the corpus into academic, textbook style.

Author: Zichun Yu, Hao Kang
Date: March 22, 2025
"""

import os
import glob
import json
import logging
from typing import List
from pathlib import Path
from vllm import SamplingParams

from sources import parsed, engine
from sources.utilities import hash_file


sampling_params = SamplingParams(
    repetition_penalty=1.2,
    temperature=0.6,
    top_p=0.95, top_k=50,
    max_tokens=2500,
)


prompt_template = \
"""Here is an extract from a webpage: "{text}".

Write an extensive and detailed course unit suitable for a textbook targeted at college students, related to the given extract. Do not just list concepts, but develop each one in detail before moving to the next, as we prioritize depth of understanding and comprehensive exploration of the subject matter over breadth. Focus on:

- Rigor: Ensure in-depth coverage of the concepts/sections.
- Engagement: Write with an academic, professional and engaging tone that captivates interest.
- Application: Incorporate specific, practical examples, such as proofs in calculus or critical dates and figures in history.
Do not include a title or an introduction, simply write the content without headlines and introductory phrases. Do not use images."""


def transform(prompts: List[str]) -> List[str]:
    outputs = engine.generate(prompts, sampling_params)
    return [item.outputs[0].text for item in outputs]


def main():
    store = Path(parsed.save_into)
    store.mkdir(mode=0o770, parents=True, exist_ok=True)
    files = sorted(filter(os.path.isfile, glob.glob(parsed.load_from)))
    files = [Path(path) for path in files]

    for i, path in enumerate(files):
        if path.suffix != ".jsonl":
            raise NotImplementedError("Only 'jsonl' files are allowed.")

        if i % parsed.task_count != parsed.task_id:
            logging.info(f"Skipping {path} as it is not my responsibility.")
            continue

        finalPath = Path(store, path.name)
        indexPath = Path(store, path.stem + ".sha256")
        if finalPath.exists() and indexPath.exists():
            finalHash = hash_file(finalPath)
            indexHash = indexPath.read_text().strip()
            if finalHash == indexHash:
                logging.info(f"Skipping {path} as it is already up-to-date.")
                continue

        prompts = list()
        logging.info(f"Reading the corpus from {path}.")
        with path.open("r") as fp:
            for line in fp:
                data = json.loads(line)
                text = prompt_template.format(text=data["text"])
                prompts.append(text)

        logging.info("Transforming the corpus into academic, textbook style.")
        outputs = transform(prompts)

        logging.info(f"Saving the corpus into {finalPath}.")
        with finalPath.open("w") as fp:
            for text in outputs:
                line = json.dumps({"text": text})
                fp.write(line + "\n")

        logging.info(f"Saving the index into {indexPath}.")
        indexHash = hash_file(finalPath)
        with indexPath.open("w") as fp:
            fp.write(indexHash)


if __name__ == '__main__':
    main()
