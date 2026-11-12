"""Small offline character n-gram Naive Bayes baseline, not a neural SOTA claim."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from corpus_workbench import normalized, select_balanced, input_key, file_hash


def features(text):
    text = normalized(text)
    return Counter(text[i:i+n] for n in (2,3) for i in range(max(0,len(text)-n+1)))


def evaluate(train, test):
    if not train or not test: raise ValueError('训练集和测试集都不能为空')
    if any(not isinstance(r['output'], str) for r in train+test):
        raise ValueError('基线只评测单标签字符串分类；多轮行为和槽位需专门指标')
    if any(r['history'] for r in train+test):
        raise ValueError('基线只评测单轮分类，不能丢弃多轮上下文')
    if {input_key(r) for r in train} & {input_key(r) for r in test}:
        raise ValueError('检测到训练测试输入重叠，请先整理隔离')
    if {r['group_id'] for r in train} & {r['group_id'] for r in test}:
        raise ValueError('检测到训练测试来源组重叠')
    docs=Counter(); counts=defaultdict(Counter); vocabulary=set()
    for row in train:
        label=row['output']; x=features(row['input']); counts[label].update(x); vocabulary.update(x); docs[label]+=1
    labels=sorted(docs); width=max(1,len(vocabulary))
    totals={label:sum(counts[label].values())+width for label in labels}
    matrix=Counter()
    for row in test:
        x={k:v for k,v in features(row['input']).items() if k in vocabulary}
        def score(label):
            return math.log(docs[label]/len(train))+sum(n*math.log((counts[label][token]+1)/totals[label]) for token,n in x.items())
        prediction=max(labels,key=score); matrix[row['output'],prediction]+=1
    per_label={}
    for label in sorted(set(labels)|{r['output'] for r in test}):
        tp=matrix[label,label]; fp=sum(v for (gold,pred),v in matrix.items() if pred==label and gold!=label)
        fn=sum(v for (gold,pred),v in matrix.items() if gold==label and pred!=label)
        per_label[label]={'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,'support':tp+fn}
    return {'model':'character 2/3-gram multinomial Naive Bayes; add-one smoothing',
            'train_records':len(train),'test_records':len(test),
            'accuracy':sum(v for (a,b),v in matrix.items() if a==b)/len(test),
            'macro_f1':sum(v['f1'] for v in per_label.values())/len(per_label),'per_label':per_label,
            'unseen_test_labels':sorted({r['output'] for r in test}-set(labels))}


def benchmark(folder, per_label=20, seeds=(11,42,73)):
    folder=Path(folder)
    def read(name):
        with (folder/name).open(encoding='utf-8') as handle: return [json.loads(line) for line in handle if line.strip()]
    train,test=read('train.jsonl'),read('test.jsonl')
    results=[]
    for seed in seeds:
        for strategy in ('random','coverage'):
            result=evaluate(select_balanced(train,per_label,seed,strategy),test)
            result.update(seed=seed,strategy=strategy); results.append(result)
    means={strategy:{metric:sum(r[metric] for r in results if r['strategy']==strategy)/len(seeds)
                     for metric in ('accuracy','macro_f1')} for strategy in ('random','coverage')}
    return {'version':'2.2.0','budget_per_label':per_label,'runs':results,'means':means,
            'dataset_hashes':{name:file_hash(folder/name) for name in ('train.jsonl','test.jsonl')},
            'limitations':'Lightweight offline baseline; no claim of neural-model improvement. Lexical coverage may equal or underperform random. Do not tune on test results.'}


def cli():
    p=argparse.ArgumentParser(description='同预算 random / coverage 离线对照实验')
    p.add_argument('folder'); p.add_argument('--per-label',type=int,default=20)
    p.add_argument('--out',required=True); a=p.parse_args()
    if Path(a.out).exists(): p.error('输出报告已存在，请更换路径')
    result=benchmark(a.folder,a.per_label)
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['means'],ensure_ascii=False,indent=2))


if __name__=='__main__': cli()
