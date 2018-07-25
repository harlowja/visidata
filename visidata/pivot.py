from visidata import *

Sheet.addCommand('W', 'pivot', 'vd.push(SheetPivot(sheet, [cursorCol]))')

# rowdef: (tuple(keyvalues), dict(variable_value -> list(rows)))
class SheetPivot(Sheet):
    'Summarize key columns in pivot table and display as new sheet.'
    rowtype = 'aggregated rows'
    def __init__(self, srcsheet, variableCols):
        super().__init__(srcsheet.name+'_pivot_'+''.join(c.name for c in variableCols), source=srcsheet)

        self.nonpivotKeyCols = []
        self.variableCols = variableCols
        for colnum, col in enumerate(srcsheet.keyCols):
            if col not in variableCols:
                newcol = copy(col)
                newcol.getter = lambda col,row,colnum=colnum: row[0][colnum]
                newcol.srccol = col
                self.nonpivotKeyCols.append(newcol)


    def reload(self):
        # two different threads for better interactive display
        self.reloadCols()
        self.reloadRows()

    @asyncthread
    def reloadCols(self):
        self.columns = copy(self.nonpivotKeyCols)
        self.keyCols = copy(self.columns)

        aggcols = [(c, aggregator) for c in self.source.visibleCols for aggregator in getattr(c, 'aggregators', [])]

        if not aggcols:
            aggcols = [(c, aggregators["count"]) for c in self.variableCols]

        for col in self.variableCols:
            for aggcol, aggregator in aggcols:
                aggname = '%s_%s' % (aggcol.name, aggregator.__name__)

                allValues = set()
                for value in Progress(col.getValues(self.source.rows), total=len(self.source.rows)):
                    if value not in allValues:
                        allValues.add(value)
                        c = Column('%s_%s' % (aggname, value),
                                type=aggregator.type or aggcol.type,
                                getter=lambda col,row,aggcol=aggcol,aggvalue=value,agg=aggregator: agg(aggcol, row[1].get(aggvalue, [])))
                        c.aggvalue = value
                        self.addColumn(c)

                if aggregator.__name__ != 'count':  # already have count above
                    c = Column('Total_' + aggname,
                                type=aggregator.type or aggcol.type,
                                getter=lambda col,row,aggcol=aggcol,agg=aggregator: agg(aggcol, sum(row[1].values(), [])))
                    self.addColumn(c)

            c = Column('Total_count',
                        type=int,
                        getter=lambda col,row: len(sum(row[1].values(), [])))
            self.addColumn(c)


    @asyncthread
    def reloadRows(self):
        rowidx = {}
        self.rows = []
        for r in Progress(self.source.rows):
            keys = tuple(keycol.srccol.getTypedValueOrException(r) for keycol in self.nonpivotKeyCols)
            formatted_keys = tuple(c.format(v) for v, c in zip(keys, self.nonpivotKeyCols))

            pivotrow = rowidx.get(formatted_keys)
            if pivotrow is None:
                pivotrow = (keys, {})
                rowidx[formatted_keys] = pivotrow
                self.addRow(pivotrow)

            for col in self.variableCols:
                varval = col.getTypedValueOrException(r)
                matchingRows = pivotrow[1].get(varval)
                if matchingRows is None:
                    pivotrow[1][varval] = [r]
                else:
                    matchingRows.append(r)

SheetPivot.addCommand('z'+ENTER, 'dive-cell', 'vs=copy(source); vs.name+="_%s"%cursorCol.aggvalue; vs.rows=cursorRow[1].get(cursorCol.aggvalue, []); vd.push(vs)')
SheetPivot.addCommand(ENTER, 'dive-row', 'vs=copy(source); vs.name+="_%s"%"+".join(cursorRow[0]); vs.rows=sum(cursorRow[1].values(), []); vd.push(vs)')
