# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import doctest
import unittest
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class StockLotDeactivatableTestCase(unittest.TestCase):
    'Test StockLotDeactivatable module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('stock_lot_deactivatable')
        self.company = POOL.get('company.company')
        self.location = POOL.get('stock.location')
        self.lot = POOL.get('stock.lot')
        self.move = POOL.get('stock.move')
        self.product = POOL.get('product.product')
        self.template = POOL.get('product.template')
        self.uom = POOL.get('product.uom')
        self.user = POOL.get('res.user')

    def test0005views(self):
        'Test views'
        test_view('stock_lot_deactivatable')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0010deactivate_lots_without_stock(self):
        'Test Lot.deactivate_lots_without_stock'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            unit, = self.uom.search([('name', '=', 'Unit')])
            template, = self.template.create([{
                        'name': 'Test Move.internal_quantity',
                        'type': 'goods',
                        'list_price': Decimal(1),
                        'cost_price': Decimal(0),
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            supplier, = self.location.search([('code', '=', 'SUP')])
            storage, = self.location.search([('code', '=', 'STO')])
            customer, = self.location.search([('code', '=', 'CUS')])
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            # Create 7 lots
            lots = self.lot.create([{
                        'number': str(x),
                        'product': product.id,
                        } for x in range(7)])

            today = date.today()
            # Create moves to get lots in storage in different dates
            # lot | -5  | -4  | -3  | -2  | -1  | today
            # ------------------------------------
            #  0  |  5  |  0  |  0  |  0  |  0  |  0
            #  1  |  5  |  2  |  0  |  0  |  0  |  0
            #  2  |  5  |  0  |  2  |  2  |  2  |  2
            #  3  |  5  | (0) | (0) | (0) | (0) | (0)
            #  4  |  5  |  5  |  0  | [2] | [2] | [2]
            #  5  |  5  |  5  |  2  | (0) | (0) | (0)
            #  6  |  5  |  5  |  5  |  0  |  0  |  0
            #  6  | [3] (without date)
            # () means assigned quantity
            # [] means draft quantity
            moves_data = [
                (lots[0], today + relativedelta(days=-5), 5, 'done'),
                (lots[0], today + relativedelta(days=-4), -5, 'done'),
                (lots[1], today + relativedelta(days=-5), 5, 'done'),
                (lots[1], today + relativedelta(days=-4), -3, 'done'),
                (lots[1], today + relativedelta(days=-3), -2, 'done'),
                (lots[2], today + relativedelta(days=-5), 5, 'done'),
                (lots[2], today + relativedelta(days=-4), -5, 'done'),
                (lots[2], today + relativedelta(days=-3), 2, 'done'),
                (lots[3], today + relativedelta(days=-5), 5, 'done'),
                (lots[3], today + relativedelta(days=-4), -5, 'assigned'),
                (lots[4], today + relativedelta(days=-5), 5, 'done'),
                (lots[4], today + relativedelta(days=-3), -5, 'done'),
                (lots[4], today + relativedelta(days=-2), 2, 'draft'),
                (lots[5], today + relativedelta(days=-5), 5, 'done'),
                (lots[5], today + relativedelta(days=-3), -3, 'done'),
                (lots[5], today + relativedelta(days=-2), -2, 'assigned'),
                (lots[6], today + relativedelta(days=-5), 5, 'done'),
                (lots[6], today + relativedelta(days=-2), -5, 'done'),
                (lots[6], None, 3, 'draft'),
                ]
            moves = self.move.create([{
                        'product': product.id,
                        'lot': lot.id,
                        'uom': unit.id,
                        'quantity': abs(quantity),
                        'from_location': (supplier.id if quantity > 0
                            else storage.id),
                        'to_location': (storage.id if quantity > 0
                            else customer.id),
                        'planned_date': planned_date,
                        'effective_date': (planned_date if state == 'done'
                            else None),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }
                    for (lot, planned_date, quantity, state) in moves_data])
            state2moves = {}
            for move, (_, _, _, state) in zip(moves, moves_data):
                state2moves.setdefault(state, []).append(move)
            self.move.do(state2moves['done'])
            self.move.assign(state2moves['assigned'])

            # reload lots
            lots = self.lot.browse([l.id for l in lots])
            self.assertTrue(all(l.active for l in lots))

            self.lot.deactivate_lots_without_stock(margin_days=6)
            lots = self.lot.browse([l.id for l in lots])
            self.assertTrue(all(l.active for l in lots))

            self.lot.deactivate_lots_without_stock(margin_days=5)
            lots = self.lot.browse([l.id for l in lots])
            self.assertTrue(all(l.active for l in lots))

            self.lot.deactivate_lots_without_stock(margin_days=4)
            lots = self.lot.browse([l.id for l in lots])
            self.assertEqual([(l.number, l.active) for l in lots], [
                    ('0', False),
                    ('1', True),
                    ('2', True),
                    ('3', True),
                    ('4', True),
                    ('5', True),
                    ('6', True),
                    ])

            self.lot.deactivate_lots_without_stock(margin_days=3)
            lots = self.lot.browse([l.id for l in lots])
            self.assertEqual([(l.number, l.active) for l in lots], [
                    ('0', False),
                    ('1', False),
                    ('2', True),
                    ('3', True),
                    ('4', True),
                    ('5', True),
                    ('6', True),
                    ])

            self.lot.deactivate_lots_without_stock(margin_days=2)
            lots = self.lot.browse([l.id for l in lots])
            self.assertEqual([(l.number, l.active) for l in lots], [
                    ('0', False),
                    ('1', False),
                    ('2', True),
                    ('3', True),
                    ('4', True),
                    ('5', True),
                    ('6', True),
                    ])

            self.lot.deactivate_lots_without_stock(margin_days=1)
            lots = self.lot.browse([l.id for l in lots])
            self.assertEqual([(l.number, l.active) for l in lots], [
                    ('0', False),
                    ('1', False),
                    ('2', True),
                    ('3', True),
                    ('4', True),
                    ('5', True),
                    ('6', True),
                    ])

            # Do assigned move of lot 3
            move = moves[9]
            assert move.lot == lots[3]
            assert move.state == 'assigned'
            move.effective_date = today + relativedelta(days=-1)
            move.save()
            self.move.do([move])

            self.lot.deactivate_lots_without_stock(margin_days=2)
            lots = self.lot.browse([l.id for l in lots])
            self.assertEqual([(l.number, l.active) for l in lots], [
                    ('0', False),
                    ('1', False),
                    ('2', True),
                    ('3', True),
                    ('4', True),
                    ('5', True),
                    ('6', True),
                    ])

            self.lot.deactivate_lots_without_stock()  # margin_days
            lots = self.lot.browse([l.id for l in lots])
            self.assertEqual([(l.number, l.active) for l in lots], [
                    ('0', False),
                    ('1', False),
                    ('2', True),
                    ('3', False),
                    ('4', True),
                    ('5', True),
                    ('6', True),
                    ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        StockLotDeactivatableTestCase))
    return suite
