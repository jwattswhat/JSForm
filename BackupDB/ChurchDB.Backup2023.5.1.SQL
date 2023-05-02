-- MariaDB dump 10.17  Distrib 10.4.10-MariaDB, for Win64 (AMD64)
--
-- Host: 192.168.3.200    Database: JSForm
-- ------------------------------------------------------
-- Server version	10.5.19-MariaDB-0+deb11u2

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `tblChoices`
--

DROP TABLE IF EXISTS `tblChoices`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tblChoices` (
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `Field` varchar(255) NOT NULL,
  `Choices` longtext NOT NULL,
  `Note` longtext DEFAULT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=MyISAM AUTO_INCREMENT=33 DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tblChoices`
--

LOCK TABLES `tblChoices` WRITE;
/*!40000 ALTER TABLE `tblChoices` DISABLE KEYS */;
INSERT INTO `tblChoices` VALUES (31,'Priority','[1\r\n2\r\n3\r\n4\r\n5]',NULL),(32,'EnteredBy','[JW]',NULL);
/*!40000 ALTER TABLE `tblChoices` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tblConfig`
--

DROP TABLE IF EXISTS `tblConfig`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tblConfig` (
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `ConfigFamily` varchar(255) NOT NULL,
  `ConfigType` varchar(100) NOT NULL,
  `ConfigValue` varchar(255) NOT NULL,
  `Note` longtext DEFAULT NULL,
  PRIMARY KEY (`ID`),
  UNIQUE KEY `Family Type` (`ConfigFamily`,`ConfigType`) USING HASH
) ENGINE=MyISAM AUTO_INCREMENT=45 DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tblConfig`
--

LOCK TABLES `tblConfig` WRITE;
/*!40000 ALTER TABLE `tblConfig` DISABLE KEYS */;
INSERT INTO `tblConfig` VALUES (4,'Location','Form','.\\Forms\\',NULL),(5,'Location','Picture','.\\Pictures\\',NULL),(6,'Location','Report','.\\Reports\\',NULL),(7,'Font','PointSize','10',NULL),(8,'Font','Family','74',NULL),(9,'Font','Style','90',NULL),(10,'Font','Weight','400',NULL),(11,'Font','Face','Calibri',NULL),(12,'Font','Underlined','False',NULL),(22,'Location','Sermon','.\\Sermons\\',NULL),(14,'Format','DateTime','%m/%d/%Y %I:%M %p','[%a - abbreviated weekday name\r\n%A - full weekday name\r\n%b - abbreviated month name\r\n%B - full month name\r\n%c - preferred date and time representation\r\n%C - century number (the year divided by 100, range 00 to 99)\r\n%d - day of the month (01 to 31)\r\n%D - same as %m/%d/%y\r\n%e - day of the month (1 to 31)\r\n%g - like %G, but without the century\r\n%G - 4-digit year corresponding to the ISO week number (see %V).\r\n%h - same as %b\r\n%H - hour, using a 24-hour clock (00 to 23)\r\n%I - hour, using a 12-hour clock (01 to 12)\r\n%j - day of the year (001 to 366)\r\n%m - month (01 to 12)\r\n%M - minute\r\n%n - newline character\r\n%p - either am or pm according to the given time value\r\n%r - time in a.m. and p.m. notation\r\n%R - time in 24 hour notation\r\n%S - second\r\n%t - tab character\r\n%T - current time, equal to %H:%M:%S\r\n%u - weekday as a number (1 to 7), Monday=1. Warning: In Sun Solaris Sunday=1\r\n%U - week number of the current year, starting with the first Sunday as the first day of the first week\r\n%V - The ISO 8601 week number of the current year (01 to 53), where week 1 is the first week that has at least 4 days in the current year, and with Monday as the first day of the week\r\n%W - week number of the current year, starting with the first Monday as the first day of the first week\r\n%w - day of the week as a decimal, Sunday=0\r\n%x - preferred date representation without the time\r\n%X - preferred time representation without the date\r\n%y - year without a century (range 00 to 99)\r\n%Y - year including the century\r\n%Z or %z - time zone or name or abbreviation\r\n%% - a literal % character]'),(15,'Format','Date','%m/%d/%Y','[%a - abbreviated weekday name\r\n%A - full weekday name\r\n%b - abbreviated month name\r\n%B - full month name\r\n%c - preferred date and time representation\r\n%C - century number (the year divided by 100, range 00 to 99)\r\n%d - day of the month (01 to 31)\r\n%D - same as %m/%d/%y\r\n%e - day of the month (1 to 31)\r\n%g - like %G, but without the century\r\n%G - 4-digit year corresponding to the ISO week number (see %V).\r\n%h - same as %b\r\n%H - hour, using a 24-hour clock (00 to 23)\r\n%I - hour, using a 12-hour clock (01 to 12)\r\n%j - day of the year (001 to 366)\r\n%m - month (01 to 12)\r\n%M - minute\r\n%n - newline character\r\n%p - either am or pm according to the given time value\r\n%r - time in a.m. and p.m. notation\r\n%R - time in 24 hour notation\r\n%S - second\r\n%t - tab character\r\n%T - current time, equal to %H:%M:%S\r\n%u - weekday as a number (1 to 7), Monday=1. Warning: In Sun Solaris Sunday=1\r\n%U - week number of the current year, starting with the first Sunday as the first day of the first week\r\n%V - The ISO 8601 week number of the current year (01 to 53), where week 1 is the first week that has at least 4 days in the current year, and with Monday as the first day of the week\r\n%W - week number of the current year, starting with the first Monday as the first day of the first week\r\n%w - day of the week as a decimal, Sunday=0\r\n%x - preferred date representation without the time\r\n%X - preferred time representation without the date\r\n%y - year without a century (range 00 to 99)\r\n%Y - year including the century\r\n%Z or %z - time zone or name or abbreviation\r\n%% - a literal % character]'),(16,'Format','Time','%I:%M %p','[%a - abbreviated weekday name\r\n%A - full weekday name\r\n%b - abbreviated month name\r\n%B - full month name\r\n%c - preferred date and time representation\r\n%C - century number (the year divided by 100, range 00 to 99)\r\n%d - day of the month (01 to 31)\r\n%D - same as %m/%d/%y\r\n%e - day of the month (1 to 31)\r\n%g - like %G, but without the century\r\n%G - 4-digit year corresponding to the ISO week number (see %V).\r\n%h - same as %b\r\n%H - hour, using a 24-hour clock (00 to 23)\r\n%I - hour, using a 12-hour clock (01 to 12)\r\n%j - day of the year (001 to 366)\r\n%m - month (01 to 12)\r\n%M - minute\r\n%n - newline character\r\n%p - either am or pm according to the given time value\r\n%r - time in a.m. and p.m. notation\r\n%R - time in 24 hour notation\r\n%S - second\r\n%t - tab character\r\n%T - current time, equal to %H:%M:%S\r\n%u - weekday as a number (1 to 7), Monday=1. Warning: In Sun Solaris Sunday=1\r\n%U - week number of the current year, starting with the first Sunday as the first day of the first week\r\n%V - The ISO 8601 week number of the current year (01 to 53), where week 1 is the first week that has at least 4 days in the current year, and with Monday as the first day of the week\r\n%W - week number of the current year, starting with the first Monday as the first day of the first week\r\n%w - day of the week as a decimal, Sunday=0\r\n%x - preferred date representation without the time\r\n%X - preferred time representation without the date\r\n%y - year without a century (range 00 to 99)\r\n%Y - year including the century\r\n%Z or %z - time zone or name or abbreviation\r\n%% - a literal % character]'),(17,'SQLFormat','DateTime','%m/%d/%Y %h:%i %p','[%a	Short weekday name in current locale (Variable lc_time_names).\r\n%b	Short form month name in current locale. For locale en_US this is one of: Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov or Dec.\r\n%c	Month with 1 or 2 digits.\r\n%D	Day with English suffix \'th\', \'nd\', \'st\' or \'rd\'\'. (1st, 2nd, 3rd...).\r\n%d	Day with 2 digits.\r\n%e	Day with 1 or 2 digits.\r\n%f	Microseconds 6 digits.\r\n%H	Hour with 2 digits between 00-23.\r\n%h	Hour with 2 digits between 01-12.\r\n%I	Hour with 2 digits between 01-12.\r\n%i	Minute with 2 digits.\r\n%j	Day of the year (001-366)\r\n%k	Hour with 1 digits between 0-23.\r\n%l	Hour with 1 digits between 1-12.\r\n%M	Full month name in current locale (Variable lc_time_names).\r\n%m	Month with 2 digits.\r\n%p	AM/PM according to current locale (Variable lc_time_names).\r\n%r	Time in 12 hour format, followed by AM/PM. Short for \'%I:%i:%S %p\'.\r\n%S	Seconds with 2 digits.\r\n%s	Seconds with 2 digits.\r\n%T	Time in 24 hour format. Short for \'%H:%i:%S\'.\r\n%U	Week number (00-53), when first day of the week is Sunday.\r\n%u	Week number (00-53), when first day of the week is Monday.\r\n%V	Week number (01-53), when first day of the week is Sunday. Used with %X.\r\n%v	Week number (01-53), when first day of the week is Monday. Used with %x.\r\n%W	Full weekday name in current locale (Variable lc_time_names).\r\n%w	Day of the week. 0 = Sunday, 6 = Saturday.\r\n%X	Year with 4 digits when first day of the week is Sunday. Used with %V.\r\n%x	Year with 4 digits when first day of the week is Monday. Used with %v.\r\n%Y	Year with 4 digits.\r\n%y	Year with 2 digits.\r\n%#	For str_to_date(), skip all numbers.\r\n%.	For str_to_date(), skip all punctation characters.\r\n%@	For str_to_date(), skip all alpha characters.\r\n%%	A literal % character.]'),(18,'SQLFormat','Date','%m/%d/%Y','[%a	Short weekday name in current locale (Variable lc_time_names).\r\n%b	Short form month name in current locale. For locale en_US this is one of: Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov or Dec.\r\n%c	Month with 1 or 2 digits.\r\n%D	Day with English suffix \'th\', \'nd\', \'st\' or \'rd\'\'. (1st, 2nd, 3rd...).\r\n%d	Day with 2 digits.\r\n%e	Day with 1 or 2 digits.\r\n%f	Microseconds 6 digits.\r\n%H	Hour with 2 digits between 00-23.\r\n%h	Hour with 2 digits between 01-12.\r\n%I	Hour with 2 digits between 01-12.\r\n%i	Minute with 2 digits.\r\n%j	Day of the year (001-366)\r\n%k	Hour with 1 digits between 0-23.\r\n%l	Hour with 1 digits between 1-12.\r\n%M	Full month name in current locale (Variable lc_time_names).\r\n%m	Month with 2 digits.\r\n%p	AM/PM according to current locale (Variable lc_time_names).\r\n%r	Time in 12 hour format, followed by AM/PM. Short for \'%I:%i:%S %p\'.\r\n%S	Seconds with 2 digits.\r\n%s	Seconds with 2 digits.\r\n%T	Time in 24 hour format. Short for \'%H:%i:%S\'.\r\n%U	Week number (00-53), when first day of the week is Sunday.\r\n%u	Week number (00-53), when first day of the week is Monday.\r\n%V	Week number (01-53), when first day of the week is Sunday. Used with %X.\r\n%v	Week number (01-53), when first day of the week is Monday. Used with %x.\r\n%W	Full weekday name in current locale (Variable lc_time_names).\r\n%w	Day of the week. 0 = Sunday, 6 = Saturday.\r\n%X	Year with 4 digits when first day of the week is Sunday. Used with %V.\r\n%x	Year with 4 digits when first day of the week is Monday. Used with %v.\r\n%Y	Year with 4 digits.\r\n%y	Year with 2 digits.\r\n%#	For str_to_date(), skip all numbers.\r\n%.	For str_to_date(), skip all punctation characters.\r\n%@	For str_to_date(), skip all alpha characters.\r\n%%	A literal % character.]'),(19,'SQLFormat','Time','%h:%i %p','[%a	Short weekday name in current locale (Variable lc_time_names).\r\n%b	Short form month name in current locale. For locale en_US this is one of: Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov or Dec.\r\n%c	Month with 1 or 2 digits.\r\n%D	Day with English suffix \'th\', \'nd\', \'st\' or \'rd\'\'. (1st, 2nd, 3rd...).\r\n%d	Day with 2 digits.\r\n%e	Day with 1 or 2 digits.\r\n%f	Microseconds 6 digits.\r\n%H	Hour with 2 digits between 00-23.\r\n%h	Hour with 2 digits between 01-12.\r\n%I	Hour with 2 digits between 01-12.\r\n%i	Minute with 2 digits.\r\n%j	Day of the year (001-366)\r\n%k	Hour with 1 digits between 0-23.\r\n%l	Hour with 1 digits between 1-12.\r\n%M	Full month name in current locale (Variable lc_time_names).\r\n%m	Month with 2 digits.\r\n%p	AM/PM according to current locale (Variable lc_time_names).\r\n%r	Time in 12 hour format, followed by AM/PM. Short for \'%I:%i:%S %p\'.\r\n%S	Seconds with 2 digits.\r\n%s	Seconds with 2 digits.\r\n%T	Time in 24 hour format. Short for \'%H:%i:%S\'.\r\n%U	Week number (00-53), when first day of the week is Sunday.\r\n%u	Week number (00-53), when first day of the week is Monday.\r\n%V	Week number (01-53), when first day of the week is Sunday. Used with %X.\r\n%v	Week number (01-53), when first day of the week is Monday. Used with %x.\r\n%W	Full weekday name in current locale (Variable lc_time_names).\r\n%w	Day of the week. 0 = Sunday, 6 = Saturday.\r\n%X	Year with 4 digits when first day of the week is Sunday. Used with %V.\r\n%x	Year with 4 digits when first day of the week is Monday. Used with %v.\r\n%Y	Year with 4 digits.\r\n%y	Year with 2 digits.\r\n%#	For str_to_date(), skip all numbers.\r\n%.	For str_to_date(), skip all punctation characters.\r\n%@	For str_to_date(), skip all alpha characters.\r\n%%	A literal % character.]'),(21,'Report','Description','.\\ReportDescription\\',NULL),(23,'Location','Outline','.\\Outlines\\',NULL),(24,'Location','Bulletin','.\\Bulletins\\',NULL),(30,'SMTP','UserName','<SMTP_USERNAME>',NULL),(29,'SMTP','Server','smtp.gmail.com',NULL),(31,'SMTP','Password','<SMTP_APP_PASSWORD>',NULL),(32,'SMTP','Port','587',NULL),(33,'License','Liturgy','000014722',NULL),(35,'SMTP','Key','<GOOGLE_API_KEY>',NULL),(36,'Location','LimeReport','C:\\Users\\jonat\\Documents\\PythonProjects\\LimeReports\\',NULL),(37,'Location','LimeReportPattern','.\\LimeReportPattern\\',NULL),(43,'Location','JSONSchema','.\\schema\\',NULL),(44,'Location','Document','.\\Documents\\',NULL);
/*!40000 ALTER TABLE `tblConfig` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tblEnhancement`
--

DROP TABLE IF EXISTS `tblEnhancement`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tblEnhancement` (
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `Description` varchar(255) DEFAULT NULL,
  `Priority` int(11) DEFAULT NULL,
  `Module` varchar(255) DEFAULT NULL,
  `Screen` varchar(255) DEFAULT NULL,
  `DateEntered` date NOT NULL,
  `DateDue` date DEFAULT NULL,
  `EnteredBy` varchar(255) DEFAULT NULL,
  `Complete` tinyint(1) NOT NULL DEFAULT 0,
  `CompleteDate` date DEFAULT NULL,
  `Note` longtext DEFAULT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB AUTO_INCREMENT=56 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tblEnhancement`
--

LOCK TABLES `tblEnhancement` WRITE;
/*!40000 ALTER TABLE `tblEnhancement` DISABLE KEYS */;
INSERT INTO `tblEnhancement` VALUES (1,'fix clsNoDataDBRecord to skip saverecord()',1,'clsDB',NULL,'2022-08-10','2022-08-10','JW',1,'2023-04-05',NULL),(2,'update forms (.json) to use \"table\" instad of \"sql\"',1,'forms',NULL,'2022-08-10','2022-08-10','JW',1,'2022-08-10',NULL),(3,'labels turn to white background on first,prev,next,last',3,'class clsForms,clsFields','frmMain.json','2022-08-10','2022-08-10','JW',1,'2022-08-10',NULL),(4,'When closing any linked form in frmService the subform frmPropers doesnt refil',1,'clsForms','frmService','2022-08-20','2022-08-20','JW',1,'2022-08-20',NULL),(6,'filepickter - show the filename only, store the directory internally.',1,'class clsFilePickerCtrl in clsFields','frmSermons.json','2022-09-10','2022-09-10','JW',1,'2022-09-10',NULL),(10,'Form for updating Checklists.',3,'New','New','2022-09-29','2022-08-10','JW',1,'2023-01-06',NULL),(11,'Fix Char spacing by font',1,'clsForm',NULL,'2022-11-06','2022-11-06','JW',1,'2022-11-06',NULL),(12,'Backup DB',1,'System',NULL,'2022-11-06','2022-11-06',NULL,1,'2022-11-06',NULL),(13,'Convert Point to Char in Screens',1,'*.json',NULL,'2022-11-06','2022-11-06','JW',1,'2022-11-06',NULL),(18,'forms clear on update ',1,'clsForm ',NULL,'2022-12-15','2022-12-15','JW',1,'2022-12-15',NULL),(20,'Add Priority to Enhancement report',2,'report generator',NULL,'2022-12-15','2022-12-15','JW',1,'2022-12-15',NULL),(22,'Firgue out what json forms belong with JSForm. Update forms to look in JSForms first.',5,'JSForm vs ChurchManager',NULL,'2022-12-17',NULL,'JW',1,'2023-04-17',NULL),(23,'Refresh on forms with no Base Record',2,'clsForms','All with no base record','2022-12-18','2022-12-15','JW',1,'2023-01-05',NULL),(24,'ComboBox Default values',3,'clsFields',NULL,'2022-12-18','2022-08-10','JW',1,'2022-12-23',NULL),(25,'Clear Warning Color on when moving to a new screen after Field changes',1,'clsForms',NULL,'2022-12-19','2022-12-15','JW',1,'2022-12-19',NULL),(26,'Refresh screen after delete record to remove deleted record',1,'clsForms',NULL,'2022-12-18','2022-12-15','JW',1,'2022-12-18',NULL),(27,'Print phone numbers with seperators.',2,'LimeReports - CMPH01',NULL,'2022-12-18','2022-12-15','JW',1,'2022-12-22',NULL),(29,'Find a way for Dates not entered to be NULL',1,'clsFields',NULL,'2022-12-19','2022-12-15','JW',1,'2022-12-19',NULL),(30,'Required Field Values',2,'clsForms, clsFields','All','2022-12-19','2022-12-15','JW',1,'2022-12-22','[Default to Required = True or False?]'),(31,'update TimePicker and DateTimePicker to allow for no entry',1,'clsFields, TimePicker, DateTimePicker',NULL,'2022-12-19','2023-04-05','JW',1,'2023-04-05',NULL),(36,'Automaticly format Phone Numbers with () -',3,'clsFields',NULL,'2022-12-22','2023-04-05','JW',1,'2022-12-23',NULL),(39,'Finish Checklists, On Merge Lists, Keep Checked Value',1,'clsFields',NULL,'2023-04-05',NULL,'JW',0,NULL,NULL),(41,'Why does Date Entered on frmBugs not default to today, like Date Due:',1,'clsForms, clsFields','frmBugs','2023-01-06','2023-04-05',NULL,1,'2023-01-04',NULL),(43,'close problems when clicking [X]',1,'clsForms',NULL,'2023-01-06',NULL,'JW',0,NULL,NULL),(44,'Page headers on Bug Report',2,'LimeReports CMEN01',NULL,'2023-01-06','2022-12-15',NULL,1,'2022-08-10',NULL),(47,'Update db for Home Landlines, and Mobile phones. ',1,'db',NULL,'2022-12-19','2023-04-05','JW',1,'2023-01-04',NULL),(50,'Highlight fields with vaild parameters on Reports screen',2,'clsForm','frmReports.json','2022-12-19',NULL,'JW',1,'2023-04-13',NULL),(52,'Implement JSONSchema',1,'json files',NULL,'2023-04-05',NULL,'JW',1,'2023-04-01','[see Jsonschema.org]'),(54,'Add Float to DB and Fields',1,'clsFields',NULL,'2023-04-05',NULL,'JW',1,'2023-04-13',NULL),(55,'Add User Entry/Edit Form and Processing',2,NULL,NULL,'2023-04-05',NULL,'JW',0,NULL,'[For Applications and JSForm]');
/*!40000 ALTER TABLE `tblEnhancement` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tblOptions`
--

DROP TABLE IF EXISTS `tblOptions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tblOptions` (
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `OptionFor` varchar(255) NOT NULL,
  `OptionType` varchar(255) NOT NULL,
  `OptionValue` longtext NOT NULL,
  `Note` longtext DEFAULT NULL,
  PRIMARY KEY (`ID`),
  UNIQUE KEY `For Type` (`OptionFor`,`OptionType`) USING HASH
) ENGINE=MyISAM AUTO_INCREMENT=8 DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tblOptions`
--

LOCK TABLES `tblOptions` WRITE;
/*!40000 ALTER TABLE `tblOptions` DISABLE KEYS */;
INSERT INTO `tblOptions` VALUES (7,'JSONSchema','CheckForms','Yes',NULL);
/*!40000 ALTER TABLE `tblOptions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tblReports`
--

DROP TABLE IF EXISTS `tblReports`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tblReports` (
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `Report` varchar(255) NOT NULL,
  `Title` varchar(255) NOT NULL,
  `Params` longtext DEFAULT NULL,
  `Batch` longtext DEFAULT NULL,
  `Note` longtext NOT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=MyISAM AUTO_INCREMENT=31 DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tblReports`
--

LOCK TABLES `tblReports` WRITE;
/*!40000 ALTER TABLE `tblReports` DISABLE KEYS */;
INSERT INTO `tblReports` VALUES (30,'JSEN01','Enhancements',NULL,NULL,'');
/*!40000 ALTER TABLE `tblReports` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2023-05-01 19:19:26
