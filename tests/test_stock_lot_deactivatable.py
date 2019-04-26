# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import doctest
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company


class StockLotDeactivatableTestCase(ModuleTestCase):
    'Test Stock Lot Deactivatable module'
    module = 'stock_lot_deactivatable'

    @with_transaction()
    def test_deactivate_lots_without_stock(self):
        pool = Pool()
        Location = pool.get('stock.location')
        Lot = pool.get('stock.lot')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')
        User= pool.get('res.user')

        company = create_company()
        with set_company(company):
            unit, = Uom.search([('name', '=', 'Unit')])
            template, = Template.create([{
                        'name': 'Test Move.internal_quantity',
                        'type': 'goods',
                        'list_price': Decimal(1),
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        }])
            product, = Product.create([{
                        'template': template.id,
                        'cost_price': Decimal(0),
                        }])
            supplier, = Location.search([('code', '=', 'SUP')])
            storage, = Location.search([('code', '=', 'STO')])
            customer, = Location.search([('code', '=', 'CUS')])
            currency = company.currency

            # Create 7 lots
            lots = Lot.create([{
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
            moves = Move.create([{
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
            Move.do(state2moves['done'])
            Move.assign(state2moves['assigned'])

            # reload lots
            lots = Lot.browse([l.id for l in lots])
            self.assertTrue(all(l.active for l in lots))

            Lot.deactivate_lots_without_stock(margin_days=6)
            lots = Lot.browse([l.id for l in lots])
            self.assertTrue(all(l.active for l in lots))

            Lot.deactivate_lots_without_stock(margin_days=5)
            lots = Lot.browse([l.id for l in lots])
            self.assertTrue(all(l.active for l in lots))

            Lot.deactivate_lots_without_stock(margin_days=4)
            lots = Lot.browse([l.id for l in lots])
            self.assertEqual([(l.number, l.active) for l in lots], [
                    ('0', False),
                    ('1', True),
                    ('2', True),
                    ('3', True),
                    ('4', True),
                    ('5', True),
                    ('6', True),
                    ])

            Lot.deactivate_lots_without_stock(margin_days=3)
            lots = Lot.browse([l.id for l in lots])
            self.assertEqual([(l.number, l.active) for l in lots], [
                    ('0', False),
                    ('1', False),
                    ('2', True),
                    ('3', True),
                    ('4', True),
                    ('5', True),
                    ('6', True),
                    ])

            Lot.deactivate_lots_without_stock(margin_days=2)
            lots = Lot.browse([l.id for l in lots])
            self.assertEqual([(l.number, l.active) for l in lots], [
                    ('0', False),
                    ('1', False),
                    ('2', True),
                    ('3', True),
                    ('4', True),
                    ('5', True),
                    ('6', True),
                    ])

            Lot.deactivate_lots_without_stock(margin_days=1)
            lots = Lot.browse([l.id for l in lots])
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
            Move.do([move])

            Lot.deactivate_lots_without_stock(margin_days=2)
            lots = Lot.browse([l.id for l in lots])
            self.assertEqual([(l.number, l.active) for l in lots], [
                    ('0', False),
                    ('1', False),
                    ('2', True),
                    ('3', True),
                    ('4', True),
                    ('5', True),
                    ('6', True),
                    ])

            Lot.deactivate_lots_without_stock()  # margin_days
            lots = Lot.browse([l.id for l in lots])
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
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockLotDeactivatableTestCase))
    return suite
