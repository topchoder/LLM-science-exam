from datasets import load_dataset
from tqdm.notebook import tqdm
import torch
import pandas as pd
from glob import glob
import numpy as np
import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from pathlib import Path

data_path = Path('/kaggle/input/kaggle-llm-science-exam')


if os.getenv('KAGGLE_IS_COMPETITION_RERUN'):
    test = pd.read_csv(data_path / 'test.csv')
    CALC_SCORE = False
else:
    test = pd.read_csv("/kaggle/input/dataset-wiki-new-1/dataset_wiki_new_1_balanced.csv")
    test["id"] = np.arange(len(test))
#     test = pd.read_csv(data_path / 'train.csv')
    CALC_SCORE = True
test.head()

test.to_parquet("test_raw.pq")

%%writefile get_topk.py

import os
import pandas as pd
from glob import glob
import torch
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from pathlib import Path
from joblib import Parallel, delayed
import argparse

if __name__ == "__main__":
    
    ap = argparse.ArgumentParser()
    ap.add_argument('--wiki', type=str, required=True)
    ap.add_argument('--model_name', type=str, required=True)
    ap.add_argument('--test_file', type=str, required=True)
    ap.add_argument('--topk', type=int, required=True)
    ap.add_argument('--ind', type=int, required=True)
    args = ap.parse_args()

    if args.ind == 1:
        TOP_K = 5 * 5
    else:
        if args.topk == 10:
            TOP_K = 20
        else:
            TOP_K = 10

    data_path = Path('/kaggle/input/kaggle-llm-science-exam')
    
    if args.wiki == "cirrus":
        print("Using cirrus wiki")
        files_all = sorted(list(glob("/kaggle/input/cirruswiki-titles/*.parquet")))
    elif args.wiki == "new":
        print("Using new wiki")
        files_all = sorted(list(glob("/kaggle/input/newwiki-titles/*.parquet")))
     elif args.wiki == "last":
        print("Using last wiki")
        files_all = sorted(list(glob("/kaggle/input/cirruswiki-256-titles/*.parquet"))) 
        
    if args.wiki == "cirrus":
        if "e5-base" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/cirruswiki-e5-part?/*.npy")))
            files_np += sorted(list(glob("/kaggle/input/cirruswiki-e5-part9-1/*.npy")))
        elif "e5-large" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/enwiki-cirrus-20230701-e5-large-part*/*.npy")))
        elif "bge-base-15" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/cirruswiki512-bge-base-en-v1-5-part*/*.npy")))
        elif "gte-base" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/cirruswiki512-gte-base-part*/*.npy")))
        elif "bge-large" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/enwiki-cirrus-20230701-bge-large-part*/*.npy")))
        elif "gte-large" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/enwiki-cirrus-20230701-gte-large-part*/*.npy")))
    elif args.wiki == "new":
        if "gte-base-title" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/gte-base-title-part*/*.npy")))
        elif "e5-base-title" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/newwiki-e5-base-title-part*/*.npy")))
        elif "e5-base" in args.model_name:
             files_np = sorted(list(glob("/kaggle/input/newwiki-e5-base-part*/*.npy")))
        elif "gte-base" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/newwiki-gte-part*/*.npy")))
        elif "gte-large" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/wiki31m-gte-large-title-p*/*.npy")))
        elif "bge-base" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/wiki31m-bge-base-title-part*/*.npy")))
        elif "e5-large" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/wiki-30-08-e5-large-title-p*/*.npy")))
        elif "bge-large" in args.model_name:
            files_np = sorted(list(glob("/kaggle/input/wiki31m-bge-large-title-p*/*.npy")))
    elif args.wiki == "last":
        files_np = sorted(list(glob("/kaggle/input/enwiki-cirrus-256-e5-base-part*/*.npy")))  

    files_all = [(x, y) for x, y in zip(files_all, files_np)]
    files = [files_all[:len(files_all)//2], files_all[len(files_all)//2:]]

    if "e5-base" in args.model_name:
        model = SentenceTransformer('/kaggle/input/intfloat-e5-base-v2').to("cuda:0")
    elif "e5-large" in args.model_name:
        model = SentenceTransformer('/kaggle/input/intfloat-e5-large-v2').to("cuda:0")
    elif "bge-base-15" in args.model_name: 
        model = SentenceTransformer('/kaggle/input/baai-bge-base-en-v1-5').to("cuda:0")
    elif "gte-base" in args.model_name: 
        model = SentenceTransformer('/kaggle/input/thenlper-gte-base').to("cuda:0")
    elif "gte-large" in args.model_name:
        model = SentenceTransformer('/kaggle/input/thenlper-gte-large').to("cuda:0")
    elif "bge-base" in args.model_name:
        model = SentenceTransformer('/kaggle/input/baai-bge-base-en').to("cuda:0")
    elif "bge-large" in args.model_name:
        model = SentenceTransformer('/kaggle/input/baai-bge-large-en').to("cuda:0")
    test = pd.read_parquet("test_raw.pq")

    embs = []
    for idx, row in tqdm(test.iterrows(), total=len(test)):
        if "e5" in args.model_name:
            if args.ind == 1:
                sentences = [
                    "query: " + row.prompt + " " + row.A,
                    "query: " + row.prompt + " " + row.B,
                    "query: " + row.prompt + " " + row.C,
                    "query: " + row.prompt + " " + row.D,
                    "query: " + row.prompt + " " + row.E,
                ]
            else:
                sentences = ["query: " + row.prompt + " " + row.A + " " + row.B + " " + row.C + " " + row.D + " " + row.E]
        elif "bge" in args.model_name:
            if args.ind == 1:
                sentences = [
                    "Represent this sentence for searching relevant passages: " + row.prompt + " " + row.A,
                    "Represent this sentence for searching relevant passages: " + row.prompt + " " + row.B,
                    "Represent this sentence for searching relevant passages: " + row.prompt + " " + row.C,
                    "Represent this sentence for searching relevant passages: " + row.prompt + " " + row.D,
                    "Represent this sentence for searching relevant passages: " + row.prompt + " " + row.E,
                ]
             else:
                sentences = ["Represent this sentence for searching relevant passages: " + row.prompt + " " + row.A + " " + row.B + " " + row.C + " " + row.D + " " + row.E]    
        elif "gte" in args.model_name:
            if args.ind == 1:
                sentences = [
                    row.prompt + " " + row.A,
                    row.prompt + " " + row.B,
                    row.prompt + " " + row.C,
                    row.prompt + " " + row.D,
                    row.prompt + " " + row.E,
                ]
            else:
                sentences = [row.prompt + " " + row.A + " " + row.B + " " + row.C + " " + row.D + " " + row.E]

        embeddings = torch.Tensor(model.encode(sentences, show_progress_bar=False, normalize_embeddings=True))
        embs.append(torch.nn.functional.normalize(embeddings, dim=1))
      if args.ind == 1:
        query_embeddings = torch.Tensor(np.concatenate(embs)).squeeze(1)
    else:
        query_embeddings = torch.Tensor(np.stack(embs)).squeeze(1)
    print(query_embeddings.shape)

    # Create placeholders for top-k matches
    all_vals_gpu_0 = torch.full((len(test), TOP_K), -float('inf'), dtype=torch.float16)
    all_texts_gpu_0 = [[None] * TOP_K for _ in range(len(all_vals_gpu_0))]

    all_vals_gpu_1 = torch.full((len(test), TOP_K), -float('inf'), dtype=torch.float16)
    all_texts_gpu_1 = [[None] * TOP_K for _ in range(len(all_vals_gpu_1))]

    print(all_vals_gpu_0.shape)
    print(len(all_texts_gpu_0))

    def cos_similarity_matrix(a: torch.Tensor, b: torch.Tensor, eps: float = 1e-8):
        """Calculates cosine similarities between tensor a and b."""
        sim_mt = torch.mm(a, b.transpose(0, 1))
        return sim_mt


    def get_topk(embeddings_from, embeddings_to, topk=1000, bs=512):
        chunk = bs
        embeddings_chunks = embeddings_from.split(chunk)

        vals = []
        inds = []
        for idx in tqdm(range(len(embeddings_chunks))):
            cos_sim_chunk = cos_similarity_matrix(embeddings_chunks[idx].to(embeddings_to.device).half(), embeddings_to).float()

            cos_sim_chunk = torch.nan_to_num(cos_sim_chunk, nan=0.0)

            topk = min(topk, cos_sim_chunk.size(1))
            vals_chunk, inds_chunk = torch.topk(cos_sim_chunk, k=topk, dim=1)
            vals.append(vals_chunk[:, :].detach().cpu())
            inds.append(inds_chunk[:, :].detach().cpu())

            del vals_chunk
            del inds_chunk
            del cos_sim_chunk
        vals = torch.cat(vals).detach().cpu()
        inds = torch.cat(inds).detach().cpu()

        return inds, vals

       def insert_value_at(tensor, value, position):
        # Ensure the position is valid
        if position < 0 or position >= len(tensor):
            raise ValueError("Position should be between 0 and tensor length - 1.")

        # Slice the tensor into two parts
        left = tensor[:position]
        right = tensor[position:]

        # Create a tensor for the value to be inserted
        value_tensor = torch.tensor([value], dtype=tensor.dtype)

        # Concatenate the tensors together and slice to the original length
        result = torch.cat([left, value_tensor, right])[:-1]

        return result


        def insert_value_at_list(lst, value, position):
        # Ensure the position is valid
        if position < 0 or position >= len(lst):
            raise ValueError("Position should be between 0 and list length - 1.")

        # Insert value at the specified position
        lst.insert(position, value)

        # Remove the last value to maintain original length
        lst.pop()

        return lst
    
    from collections import OrderedDict

    def get_first_5_unique_strings(input_list):
#         print(len(input_list))
        unique_strings = list(OrderedDict.fromkeys(input_list))
#         print(unique_strings)
        while len(unique_strings) < args.topk:
            # TODO: check why this is ever happening
            unique_strings.append("No context found")
            print("appending None")
        return unique_strings[:args.topk]

    
