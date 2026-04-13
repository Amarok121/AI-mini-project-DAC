def combine_credibility(sci: str, ind: str) -> str:
    table = {
        ('HIGH', 'HIGH'): 'HIGH',
        ('HIGH', 'MED'): 'MED',
        ('HIGH', 'LOW'): 'MED',
        ('MED', 'HIGH'): 'MED',
        ('MED', 'MED'): 'MED',
        ('MED', 'LOW'): 'LOW',
        ('LOW', 'HIGH'): 'MED',
        ('LOW', 'MED'): 'LOW',
        ('LOW', 'LOW'): 'LOW',
    }
    return table.get((sci, ind), 'LOW')
