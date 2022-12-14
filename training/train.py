from copy import deepcopy

#computing
import numpy as np

#scikit learn
from sklearn.metrics import roc_auc_score

#weights and biases
import wandb

#ray
import ray


def train(model, train_step, model_predict, dataloaders_id, optimizer, args, save_best=False, verbose=True):

    dataloaders = ray.get(dataloaders_id)

    #initialize maximum validation value
    val_max = 0
    best_model = model

    #iterate over epochs
    for epoch in range(1, args["epochs"]):

        #iterate over batchs (of networks)
        for i, batch in enumerate(dataloaders['train']):
            
           #take a training step
           loss = train_step(model, batch, optimizer, args)

        #get training loss/ training auroc & validation auroc
        log = 'Epoch: {:03d}, Train: {:.4f}, Val: {:.4f}, Loss: {:.5f}'
        score_train = test(model, model_predict, dataloaders['train'], args)
        score_val = test(model, model_predict, dataloaders['val'], args)
        
        #log metrics to weigths and biases
        wandb.log({"loss": float(loss.item())})
        wandb.log({"auroc_train": score_train})
        wandb.log({"auroc_val": score_val})

        #print if set to verbose
        if verbose:
          print(log.format(epoch, score_train, score_val, loss.item()))

        #delete batch and loss
        del batch
        del loss

        #is save_best is true then we save the best model
        if val_max < score_val and save_best:
            val_max = score_val
            best_model = deepcopy(model)
            

    #at the end of training log roc curve
    _ = test(model, model_predict, dataloaders['val'], args, roc=True)

    return score_val


def test(model, model_predict, dataloader, args, roc=False):

    #initialize score and number of batchs to 0
    score = 0
    num_batches = 0

    #initialize list of ground truths and predictions
    preds = []
    grounds = []

    #iterate over the testing batch (of networks)
    for batch in dataloader:

        #predictions
        pred = model_predict(model, batch, args)

        #get ground truth and predictions and send them to the cpu
        ground_truth = batch.edge_label.flatten().cpu().numpy()
        predictions = pred.flatten().data.cpu().numpy()

        #compute batch auroc score
        score += roc_auc_score(ground_truth, predictions)

        #append the predictions and ground scores
        preds.append(predictions)
        grounds.append(ground_truth)
        
        #increment number of batches
        num_batches += 1

    #compute score    
    score /= num_batches 

    #if we want to plot the roc
    if roc:
      ground_truth = np.concatenate(grounds).astype(int)
      predictions = np.concatenate(preds)
      predictions = np.vstack([1 - predictions, predictions]).T

      wandb.log({"roc" : wandb.plot.roc_curve(ground_truth, predictions,
                        labels=['no link', 'link'], classes_to_plot=[1])})
    return score