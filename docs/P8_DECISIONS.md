# P8 Decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| scenario_id as split group | enforced | Repeated scenario runs | run_id / random split | Never for V1 |
| 60/20/20 approximate group split | yes | Balance + class coverage | 70/15/15 | More scenarios |
| locked test set | enforced | Prevent contamination | Use test for tuning | Never |
| train-only TF-IDF | enforced | Vocabulary leakage | Fit on all | Never |
| train-only scaler | enforced | Mean/scale leakage | Fit on all | Never |
| fixed hyperparameters | enforced | Small-n, no search | GridSearchCV | More data + nested CV |
| no SMOTE | enforced | Preserve real counts | Oversample | P9 evidence |
| no class weighting baseline | `None` | Mild imbalance | `balanced` | P9 ablation |
| hybrid LR primary baseline | yes | Interpretable hybrid | SVM primary | P9 results |
| text/behavior LR ablations | trained | Attribution | Skip ablations | Resource limits |
| LinearSVM hybrid | trained | Linear comparator | RBF SVM | Complexity |
| NB text only | trained | Classic text baseline | Hybrid NB | Negative features |
| RF behavior only | trained | Non-linear behavior | RF hybrid densified | Memory |
| no winner in P8 | enforced | Needs evaluation | Pick by train score | Never |
| no test metrics | enforced | P9 ownership | Peek test F1 | Never |
| batch overlap allowed | documented | Batches mix classes | Batch-exclusive | Strong batch effects |
