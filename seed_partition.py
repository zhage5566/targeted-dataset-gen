"""Stable, auditable lineage grouping; only hashes and assignments are persisted."""
import hashlib
import re
import sqlite3
from pathlib import Path
import scenes as S
from language_support import EN_PRODUCTS, EN_CITIES


class SeedPartition:
    def __init__(self, mode='train', test_fraction=.2, split_seed=42, path=None, readonly=False):
        if mode not in ('train','test','all'): raise ValueError('种子划分须为 train、test 或 all')
        if not isinstance(test_fraction,(int,float)) or not 0 < test_fraction < 1:
            raise ValueError('测试种子比例须大于 0 且小于 1')
        self.mode, self.fraction, self.seed = mode, test_fraction, int(split_seed)
        self.cache, self.db = {}, None
        self.path = str(path) if path else None
        self.readonly = readonly
        if path and mode != 'all':
            path = Path(path).expanduser().resolve()
            if not readonly:
                path.parent.mkdir(parents=True,exist_ok=True)
                self.db = sqlite3.connect(path)
                self.db.execute('CREATE TABLE IF NOT EXISTS seed_groups (fingerprint TEXT PRIMARY KEY, partition TEXT NOT NULL, seed INTEGER NOT NULL, fraction REAL NOT NULL)')
                self.db.commit()
            elif path.is_file():
                self.db = sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
        vocabulary = S.PRODUCTS + S.CITIES + S.BRANDS + EN_PRODUCTS + EN_CITIES
        self.entities = re.compile('|'.join((r'\b'+re.escape(v)+r'\b') if v.isascii() else re.escape(v)
                                           for v in sorted(set(vocabulary),key=len,reverse=True)),re.I)

    def existing(self,group):
        if group in self.cache: return self.cache[group]
        row = self.db.execute('SELECT partition FROM seed_groups WHERE fingerprint=?',(group,)).fetchone() if self.db else None
        return row[0] if row else None

    def store(self,group,assigned):
        prior = self.existing(group)
        if prior and prior != assigned: raise ValueError('分组冲突：该输入结构已分配到另一侧')
        if self.db and not self.readonly and not prior:
            self.db.execute('INSERT OR IGNORE INTO seed_groups VALUES (?,?,?,?)',(group,assigned,self.seed,self.fraction))
            self.db.commit()
            prior = self.db.execute('SELECT partition FROM seed_groups WHERE fingerprint=?',(group,)).fetchone()[0]
            if prior != assigned: raise ValueError('分组冲突：该输入结构已分配到另一侧')
        self.cache[group] = assigned

    def prepare(self,sample,core,explicit=None):
        group = self.group(sample,core,explicit)
        structure = self.group(sample,core)
        group_prior, structure_prior = self.existing(group), self.existing(structure)
        if group_prior and structure_prior and group_prior != structure_prior:
            raise ValueError('分组冲突：来源分组与输入结构处于不同侧')
        assigned = group_prior or structure_prior or self.assign(group)
        self.store(group,assigned)
        self.store(structure,assigned)
        return group,assigned

    def group(self, sample, core, explicit=None):
        if explicit is not None:
            if not isinstance(explicit,(str,int)) or not str(explicit).strip(): raise ValueError('group_id 必须是非空字符串或整数')
            raw = 'explicit:'+str(explicit).strip()
        else:
            # Exclude system/task so the same input used by two classifiers stays together.
            texts = []
            for message in sample.obj['messages'][1:-1]:
                text = message['content']
                # Grounded labels also mask custom vocabulary unknown to built-in lists.
                if sample.task in ('intent','slots'):
                    answer=core.json.loads(sample.answer)
                    entities=sorted(set(answer.get('slots',{}).values()),key=len,reverse=True)
                    if entities: text=re.sub('|'.join(re.escape(v) for v in entities if v),'<entity>',text)
                text = self.entities.sub('<entity>',text)
                text = re.sub(r'(?:卡尾号|账户尾号)\d+|(?:card|account) ending \d+', '<identifier>',text,flags=re.I)
                text = re.sub(r'\b[A-Z]{2,12}-[A-Z0-9_-]{4,}\b','<identifier>',text,flags=re.I)
                text = re.sub(r'\d+(?:\.\d+)?','<number>',text)
                texts.append({'role':message['role'],'content':core.canonical(text)})
            raw = 'structure:'+core.dumps(texts)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def assign(self, group):
        if group in self.cache: return self.cache[group]
        prior = self.db.execute('SELECT partition FROM seed_groups WHERE fingerprint=?',(group,)).fetchone() if self.db else None
        if prior: assigned = prior[0]
        else:
            number = int.from_bytes(hashlib.sha256((str(self.seed)+':'+group).encode()).digest()[:8],'big')/2**64
            assigned = 'test' if number < self.fraction else 'train'
            if self.db and not self.readonly:
                self.db.execute('INSERT OR IGNORE INTO seed_groups VALUES (?,?,?,?)',(group,assigned,self.seed,self.fraction))
                # Commit assignments independently of data generation, preserving stable lineage.
                self.db.commit()
                assigned = self.db.execute('SELECT partition FROM seed_groups WHERE fingerprint=?',(group,)).fetchone()[0]
        self.cache[group] = assigned
        return assigned

    def allows(self, sample, core):
        if self.mode == 'all': return True
        group = sample.seed_group or self.group(sample,core)
        sample.seed_group = group
        sample.seed_split = self.assign(group)
        return sample.seed_split == self.mode

    def close(self):
        if self.db:
            self.db.close()
            self.db = None
