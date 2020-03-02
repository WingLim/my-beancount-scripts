from datetime import date
from beancount.core import data
from beancount.core.data import Transaction, Note
from .deduplicate import Deduplicate
from .base import Base
from . import DictReaderStrip, get_account_by_guess, get_income_account_by_guess
from io import StringIO
from ..accounts import accounts
import csv
import dateparser
import calendar
import pdb

class ICBCDebit2(Base):

	def __init__(self, filename, byte_content, entries, option_map):
		content = byte_content.decode('utf-8-sig')
		lines = content.split("\r\n")
		lines[6] = lines[6] + ','
		if ('621226' not in lines[2]):
			raise 'Not ICBC!'
		content = "\n".join(lines[6:len(lines) - 3])
		self.account = '工商银行({})'.format(lines[2][19:23])
		self.content = content
		self.deduplicate = Deduplicate(entries, option_map)

	def change_currency (self, currency):
		if currency == '人民币':
			return 'CNY'
		return currency
	
	def parse(self):
		content = self.content
		f = StringIO(content)
		reader = DictReaderStrip(f, delimiter=',')
		transactions = []
		trade_account = accounts[self.account]
		for row in reader:
			time = row['交易日期']
			print("Importing {} at {}".format(row['交易场所'], time))
			time = dateparser.parse(time)
			meta = {}
			meta = data.new_metadata(
				'beancount/core/testing.beancount',
				12345,
				meta
			)
			flag = "*"
			account = get_account_by_guess(row['对方户名'], row['交易场所'], time)
			trade_currency = self.change_currency(row['记账币种'])
			entry = Transaction(
				meta,
				date(time.year, time.month, time.day),
				flag,
				row['对方户名'],
				row['交易场所'],
				data.EMPTY_SET,
				data.EMPTY_SET, []

			)
			# pdb.set_trace()
			data.create_simple_posting(entry, account, None, None)
			if row['记账金额(支出)'] != '':
				trade_price = "-"+row['记账金额(支出)'].replace(',', '')
				data.create_simple_posting(entry, trade_account, trade_price, trade_currency)
			else:
				trade_price = "-"+row['记账金额(收入)'].replace(',', '')
				income = get_income_account_by_guess(row['对方户名'], row['交易场所'], time)
				if income == 'Income:Unknown':
					entry = entry._replace(flag = '!')
				data.create_simple_posting(entry, income, trade_price, trade_currency)
			
			amount = float(trade_price)

			if not self.deduplicate.find_duplicate(entry, amount, None, trade_account):
				transactions.append(entry)
		
		self.deduplicate.apply_beans()
		return transactions
