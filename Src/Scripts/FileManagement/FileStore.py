import os
import popen2
import win32ver
import dircache
import shutil
import string
import time
import datetime
import hashlib

import FileStoreDatabase

class FileProcessor:
	DebugLevel = 2
	NotInterestedFiles = [ 'spmsg.dll', 'spuninst.exe', 'spcustom.dll', 'update.exe', 'updspapi.dll', 'HotFixInstallerUI.dll' ]
	Database = None

	def __init__( self, databasename = None, database = None ):
		if self.DebugLevel > 3:
			print 'FileProcessor', databasename, database
		if database:
			self.Database = database
		else:
			self.Database = FileStoreDatabase.Database( databasename )

	def IsExecutable( self , filename ):
		try:
			fd = open( filename, "rb" )
			header = fd.read(2)
			fd.close()
			
			if header == 'MZ':
				return True
		except:
			pass

		return False

	def GetMD5( self , data ):
		m = hashlib.md5()
		m.update( data )
		return m.hexdigest()		

	def GetSHA1( self , data ):
		s = hashlib.sha1()
		s.update( data )
		return s.hexdigest()

	def SanitizeForFilename( self, name ):
		ret = ''
		only_spaces = True

		for ch in name:
			n = ord(ch)
			if ( ord('a') <= n and n <= ord('z') ) or \
					( ord('A') <= n and n <= ord('Z') ) or \
					( ord('0') <= n and n <= ord('9') ) or \
					ch == ' ' or \
					ch == '(' or \
					ch == ')' or \
					ch == ',' or \
					ch == '.':
				ret += ch
			else:
				ret += '_'
				
			if ch != ' ':
				only_spaces = False
		
		if only_spaces:
			ret = '_'
		return ret

	def CheckInFiles( self, src_dirname, storage_root = None, download = None, copy_file = True, overwrite_mode = True, tags=[], message_callback=None, message_callback_arg=None ):
		if not os.path.isdir( src_dirname ):
			return 

		for file in dircache.listdir( src_dirname ):
			src_filename = os.path.join( src_dirname, file )
			if os.path.isdir( src_filename ):
				try:
					self.CheckInFiles( os.path.join( src_dirname, file ), storage_root, download, copy_file = copy_file, overwrite_mode = overwrite_mode, tags=tags, message_callback=message_callback, message_callback_arg=message_callback_arg )
				except:
					import traceback

					if message_callback!=None:
						message_callback(message_callback_arg, traceback.format_exc())
					else:
						traceback.print_exc()
					continue

			elif self.IsExecutable( src_filename ):
				#Check MZ at the start of the file
				if self.DebugLevel > 2:
					print src_filename

				filename = os.path.basename( src_filename )
				
				if not filename in self.NotInterestedFiles:
					version_info = self.QueryFile( src_filename )
					
					try:
						statinfo = os.stat( src_filename )
						if self.DebugLevel > 2:
							print "%s=%s,%s" % ( file, time.ctime(statinfo.st_ctime), time.ctime(statinfo.st_mtime) )

						ctime = time.localtime( statinfo.st_ctime )
						ctime_dt = datetime.datetime( ctime.tm_year, ctime.tm_mon, ctime.tm_mday, ctime.tm_hour, ctime.tm_min, ctime.tm_sec )

						mtime = time.localtime( statinfo.st_mtime )
						mtime_dt = datetime.datetime( mtime.tm_year, mtime.tm_mon, mtime.tm_mday, mtime.tm_hour, mtime.tm_min, mtime.tm_sec )

						added_time = time.localtime( time.time() )
						added_time_dt = datetime.datetime( added_time.tm_year, added_time.tm_mon, added_time.tm_mday, added_time.tm_hour, added_time.tm_min, added_time.tm_sec )

						fd = open( src_filename, "rb" )
						data = fd.read()
						fd.close()
						md5 = self.GetMD5( data )
						sha1 = self.GetSHA1( data )

						if self.DebugLevel > 2:
							print version_info

						if not sha1:
							continue

						#Put to the Index Database
						operating_system = 'Windows XP'
						patch_identifier = ''
						service_pack = ''
						company_name = ''
						file_version = ''
						if version_info.has_key( 'CompanyName' ) and version_info.has_key( 'FileVersion' ):
							company_name = version_info['CompanyName']
							file_version = version_info['FileVersion']

						files = self.Database.GetFileBySHA1( sha1, None,None,None,None,None )

						if not storage_root:
							storage_root = os.getcwd()

						target_relative_directory = "%s\\%s\%s\\%s\\%s" % (sha1[0:2],sha1[2:4],sha1[4:6],sha1[6:8],sha1[8:])
						target_relative_filename = os.path.join( target_relative_directory,  os.path.basename(src_filename))

						target_full_directory = os.path.join( storage_root, target_relative_directory )
						target_full_filename = os.path.join( storage_root, target_relative_filename )
							
						if not os.path.isfile(target_full_filename) or not files or len(files) == 0 or overwrite_mode:
							if not os.path.isdir( target_full_directory ):
								try:
									os.makedirs( target_full_directory )
								except:
									print 'Failed to make',target_full_directory

							if src_filename.lower() != target_full_filename.lower():
								if self.DebugLevel > 1:
									if copy_file:
										op="Copy"
									else:
										op="Move"
								
									message="%s\n   %s\n   %s\n" % (op, src_filename, target_full_filename)

									if message_callback!=None:
										message_callback(message_callback_arg, message)
									else:
										print message
								try:
									if copy_file:
										shutil.copyfile( src_filename, target_full_filename )
									else:
										shutil.move( src_filename, target_full_filename )
								except:
									import traceback

									if self.DebugLevel > -1:

										message = '%s %s -> %s' % (op, src_filename, target_full_filename)

										if message_callback!=None:
											message_callback(message_callback_arg, message)
										else:
											print message

									if message_callback!=None:
										message_callback(message_callback_arg, traceback.format_exc())
									else:
										traceback.print_exc()

						import pefile
						pe = pefile.PE(src_filename)
						_32bitFlag = pefile.IMAGE_CHARACTERISTICS['IMAGE_FILE_32BIT_MACHINE']

						if ( pe.FILE_HEADER.Machine & _32bitFlag ) == _32bitFlag:
							arch="x86"
						else:
							arch="64"

						if files and len(files)>0:
							if self.DebugLevel > 2:
								print 'Already there:', src_filename, version_info,sha1,files

							for file in files:
								# timestamp comparision and update
								if file.mtime < mtime_dt or overwrite_mode:
									if self.DebugLevel > 2:
										print 'Updating with older data:', src_filename, version_info
								
									self.Database.UpdateFileByObject(
										file,
										download,
										arch,
										operating_system, 
										service_pack, 
										filename, 
										company_name,
										file_version,
										patch_identifier,
										src_filename,
										target_relative_filename,
										ctime = ctime_dt,
										mtime = mtime_dt,
										added_time = added_time_dt,
										md5 = md5,
										sha1 = sha1,
										tags = tags
									)
						else:
							self.Database.AddFile( 
								download,
								arch,
								operating_system, 
								service_pack, 
								filename, 
								company_name, 
								file_version, 
								patch_identifier,
								src_filename,
								target_relative_filename,
								ctime = ctime_dt,
								mtime = mtime_dt,
								added_time = added_time_dt,
								md5 = md5,
								sha1 = sha1,
								tags = tags
							)

					except:
						import traceback
						if message_callback!=None:
							message_callback(message_callback_arg, traceback.format_exc())
						else:
							traceback.print_exc()

		self.Database.Commit()

	def QueryFile( self, filename ):
		VersionInfo = {}
		info = win32ver.GetFileVersionInfo( filename )
		if info:
			lclists = []
			lclists.append( win32ver.VerQueryValue( info ) )
			lclists.append( [(1033,0x04E4)] )

			try:
				for lclist in lclists:
					if self.DebugLevel > 5:
						print 'lclist', lclist
					block = u"\\StringFileInfo\\%04x%04x\\" % lclist[0]
					for s in ( "CompanyName", "Company", "FileVersion", "File Version", "ProductVersion" ):
						value = win32ver.VerQueryValue( info, block+s)
						if self.DebugLevel > 5:
							print "\t", s,'=',value
						if value and not VersionInfo.has_key( s ):
							VersionInfo[s] = value
			except:
				pass
		return VersionInfo

if __name__=='__main__':
	from optparse import OptionParser
	import sys

	parser=OptionParser()
	parser.add_option('-s','--store',
					dest='store',help="Store files to the depot", 
					action="store_true", default=False, 
					metavar="STORE")

	parser.add_option('-t','--tags',
					dest='tags',help="Set tags files", 
					default="", 
					metavar="TAGS")

	parser.add_option('-T','--test',
					dest='test',help="Test functionalities", 
					action="store_true", default=False, 
					metavar="TEST")

	(options,args)=parser.parse_args()

	if options.store:
		file_store = FileProcessor( databasename = r'index.db' )

		src_dirname = args[0]
		storage_root = args[1]

		tags=options.tags.split(',')
		print 'Store: %s -> %s (tags:%s)' % (src_dirname, storage_root, ','.join(tags))
		file_store.CheckInFiles( src_dirname, storage_root = storage_root, tags=tags )

	elif options.test:
		import unittest, sys, os

		# These strings are rather system dependant.
		EXPECTEDSTRINGS = [
			("OriginalFilename", "REGEDIT.EXE"),
			("ProductVersion", "5.00.2134.1"),
			("FileVersion", "5.00.2134.1"),
			("FileDescription", "Registry Editor"),
			("Comments", None),
			("InternalName", "REGEDIT"),
			#("ProductName", "Microsoft(R) Windows (R) 2000 Operating System"),
			("CompanyName", "Microsoft Corporation"),
			("LegalCopyright", "Copyright (C) Microsoft Corp. 1981-1999"),
			("LegalTrademarks", None),
			#("PrivateBuild", None),
			("SpecialBuild", None)]

		TESTFILE = os.path.join(os.environ['windir'], 'regedit.exe')

		class Win32VerTest(unittest.TestCase):
			def setUp(self):
				self.info = win32ver.GetFileVersionInfo( TESTFILE )
				assert(self.info is not None)

			def tearDown(self):
				pass

			def testLCList(self):
				'''Retrive language codepair list'''
				# Calling VerQueryValue with no path should return a list
				# of language, codepage pairs.
				lclist = win32ver.VerQueryValue(self.info)
				print 'lclist', lclist
				self.assertEquals(lclist, [(1033, 1200)])

			def testValues(self):
				'''Retrieve version strings'''
				lclist = win32ver.VerQueryValue(self.info)
				block = u"\\StringFileInfo\\%04x%04x\\" % lclist[0]
				for s, expected in EXPECTEDSTRINGS:
					value = win32ver.VerQueryValue(self.info, block+s)
					print s, value
					#self.assertEquals(value, expected)
