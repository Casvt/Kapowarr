-- ********************************************************************
-- Ensure that the database names are correct for your mysql setup
-- This script assumes your databases are named:
--      Ombi
--      Ombi_Settings
--      Ombi_External
-- Change them if yours are different.
-- ********************************************************************

-- Ombi Database
DROP TABLE IF EXISTS `Ombi`.`__EFMigrationsHistory`;
CREATE TABLE `Ombi`.`__EFMigrationsHistory` (
  `MigrationId` varchar(150) NOT NULL,
  `ProductVersion` varchar(32) NOT NULL,
  PRIMARY KEY (`MigrationId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
LOCK TABLES `Ombi`.`__EFMigrationsHistory` WRITE;
INSERT INTO `Ombi`.`__EFMigrationsHistory` VALUES 
('20191102235852_Inital','3.1.8'),
('20200218230644_MobileDevices','3.1.8'),
('20200516194814_IssueCreatedDate','3.1.8'),
('20200610223540_UserProfile','3.1.8'),
('20200731151314_RemoveEmbyConnectionid','3.1.8'),
('20200829205234_Charset','3.1.8'),
('20210106132735_UserStreamingCountry','5.0.1'),
('20210305151743_TvRequestProviderId','5.0.1'),
('20210408073336_SonarrProfileOnRequest','5.0.1'),
('20210921200723_UserRequestLimits','5.0.1'),
('20210922091445_UserRequestLimits_Pt2','5.0.1');
UNLOCK TABLES;

-- Ombi_Settings Database
DROP TABLE IF EXISTS `Ombi_Settings`.`__EFMigrationsHistory`;
CREATE TABLE `Ombi_Settings`.`__EFMigrationsHistory` (
  `MigrationId` varchar(150) NOT NULL,
  `ProductVersion` varchar(32) NOT NULL,
  PRIMARY KEY (`MigrationId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
LOCK TABLES `Ombi_Settings`.`__EFMigrationsHistory` WRITE;
INSERT INTO `Ombi_Settings`.`__EFMigrationsHistory` VALUES ('20191103205915_Inital','3.1.8');
UNLOCK TABLES;

-- Ombi_External Database
DROP TABLE IF EXISTS `Ombi_External`.`__EFMigrationsHistory`;
CREATE TABLE `Ombi_External`.`__EFMigrationsHistory` (
  `MigrationId` varchar(150) NOT NULL,
  `ProductVersion` varchar(32) NOT NULL,
  PRIMARY KEY (`MigrationId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
LOCK TABLES `Ombi_External`.`__EFMigrationsHistory` WRITE;
INSERT INTO `Ombi_External`.`__EFMigrationsHistory` VALUES ('20191103213915_Inital','5.0.1'),('20210103205509_Jellyfin','5.0.1'),('20210615152049_SonarrSyncMovieDbData','5.0.1');
UNLOCK TABLES;