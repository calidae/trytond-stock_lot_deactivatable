# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import ir
from . import stock


def register():
    Pool.register(
        ir.Cron,
        stock.Lot,
        stock.Move,
        stock.Period,
        module='stock_lot_deactivatable', type_='model')
