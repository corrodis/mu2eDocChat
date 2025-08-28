from datasets import load_dataset, load_from_disk
from sentence_transformers import SentenceTransformer
from sentence_transformers.losses import TripletLoss, MultipleNegativesRankingLoss
from sentence_transformers.evaluation import TripletEvaluator, SimilarityFunction
from sentence_transformers.training_args import SentenceTransformerTrainingArguments, BatchSamplers
from sentence_transformers.trainer import SentenceTransformerTrainer




#starting model
model = SentenceTransformer("sentence-transformers/multi-qa-mpnet-base-dot-v1")

#initializing loss function
loss = MultipleNegativesRankingLoss(model)

#load dataset
dataset = load_from_disk("/home/newg2/.mu2e/data/training_dataset.json")

split = dataset.train_test_split(test_size=0.20, seed=42)

#dev_test = DatasetDict({"dev": split["train"], "test": split["test"]})

train_dataset = split["train"]
test_dataset = split["test"]

# Just before passing datasets to the trainer:
train_dataset = train_dataset.remove_columns(["negative"])
test_dataset = test_dataset.remove_columns(["negative"])


print("Dev size:", len(train_dataset), " Test size:", len(test_dataset))



#specify training arguments here

args = SentenceTransformerTrainingArguments(
    # Required parameter:
    output_dir="models/mpnet-base-all-nli-triplet",
    # Optional training parameters:
    num_train_epochs=1,
    per_device_train_batch_size=2,
    per_device_eval_batch_size=2,
    learning_rate=2e-5,
    warmup_ratio=0.1,
    fp16=True,  # Set to False if you get an error that your GPU can't run on FP16
    bf16=False,  # Set to True if you have a GPU that supports BF16
    batch_sampler=BatchSamplers.NO_DUPLICATES,  # MultipleNegativesRankingLoss benefits from no duplicate samples in a batch
    # Optional tracking/debugging parameters:
    eval_strategy="steps",
    eval_steps=100,
    save_strategy="step",
    save_steps=100,
    save_total_limit=2,
    logging_steps=100,
    run_name="mpnet-base-all-nli-triplet",  # Will be used in W&B if `wandb` is installed
)


#create trainer & train
trainer = SentenceTransformerTrainer(
    model=model,
    args=args,
    train_dataset=train_dataset,
    loss=loss,
)

trainer.train()

trainer.evaluate(test_dataset)


model.save_pretrained("models/multi-qa-mpnet-base-dot-v1-mu2e")
