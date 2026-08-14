DROP TABLE IF EXISTS sb_student;
DROP TABLE IF EXISTS sb_route_stop;
DROP TABLE IF EXISTS sb_route;
DROP TABLE IF EXISTS sb_bus;
DROP TABLE IF EXISTS sb_driver;
DROP TABLE IF EXISTS sb_school;

CREATE TABLE sb_school (
    ID INT NOT NULL AUTO_INCREMENT,
    Name VARCHAR(120) NOT NULL,
    Phone VARCHAR(50) NULL,
    Address VARCHAR(180) NULL,
    Active TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (ID), UNIQUE KEY uq_sb_school_name (Name)
) ENGINE=InnoDB;

CREATE TABLE sb_driver (
    ID INT NOT NULL AUTO_INCREMENT,
    FirstName VARCHAR(60) NOT NULL,
    LastName VARCHAR(60) NOT NULL,
    Phone VARCHAR(50) NULL,
    Email VARCHAR(254) NULL,
    HireDate DATE NULL,
    Active TINYINT(1) NOT NULL DEFAULT 1,
    Note TEXT NULL,
    PRIMARY KEY (ID)
) ENGINE=InnoDB;

CREATE TABLE sb_bus (
    ID INT NOT NULL AUTO_INCREMENT,
    BusNumber VARCHAR(20) NOT NULL,
    Capacity INT NOT NULL,
    Accessible TINYINT(1) NOT NULL DEFAULT 0,
    Active TINYINT(1) NOT NULL DEFAULT 1,
    Note TEXT NULL,
    PRIMARY KEY (ID), UNIQUE KEY uq_sb_bus_number (BusNumber)
) ENGINE=InnoDB;

CREATE TABLE sb_route (
    ID INT NOT NULL AUTO_INCREMENT,
    SchoolID INT NOT NULL,
    Name VARCHAR(100) NOT NULL,
    TripType VARCHAR(20) NOT NULL,
    BusID INT NULL,
    DriverID INT NULL,
    StartTime TIME NULL,
    Active TINYINT(1) NOT NULL DEFAULT 1,
    Note TEXT NULL,
    PRIMARY KEY (ID),
    CONSTRAINT fk_sb_route_school FOREIGN KEY (SchoolID) REFERENCES sb_school(ID),
    CONSTRAINT fk_sb_route_bus FOREIGN KEY (BusID) REFERENCES sb_bus(ID),
    CONSTRAINT fk_sb_route_driver FOREIGN KEY (DriverID) REFERENCES sb_driver(ID)
) ENGINE=InnoDB;

CREATE TABLE sb_route_stop (
    ID INT NOT NULL AUTO_INCREMENT,
    RouteID INT NOT NULL,
    SequenceNumber INT NOT NULL,
    StopName VARCHAR(100) NOT NULL,
    Address VARCHAR(180) NULL,
    StopTime TIME NULL,
    PRIMARY KEY (ID),
    UNIQUE KEY uq_sb_route_stop_sequence (RouteID, SequenceNumber),
    CONSTRAINT fk_sb_stop_route FOREIGN KEY (RouteID) REFERENCES sb_route(ID) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE sb_student (
    ID INT NOT NULL AUTO_INCREMENT,
    FirstName VARCHAR(60) NOT NULL,
    LastName VARCHAR(60) NOT NULL,
    Grade VARCHAR(12) NULL,
    EmergencyPhone VARCHAR(50) NULL,
    RouteStopID INT NULL,
    Active TINYINT(1) NOT NULL DEFAULT 1,
    Note TEXT NULL,
    PRIMARY KEY (ID),
    CONSTRAINT fk_sb_student_stop FOREIGN KEY (RouteStopID) REFERENCES sb_route_stop(ID)
) ENGINE=InnoDB;

INSERT INTO sb_school (Name,Phone,Address) VALUES
('Pine Valley Elementary','5550101000','100 Learning Lane'),
('Pine Valley Middle School','5550102000','200 Timber Road');

INSERT INTO sb_driver (FirstName,LastName,Phone,Email,HireDate,Note) VALUES
('Morgan','Lee','5550103001','morgan.lee@example.test','2022-08-15','Morning route specialist'),
('Casey','Rivera','5550103002','casey.rivera@example.test','2024-01-08',NULL);

INSERT INTO sb_bus (BusNumber,Capacity,Accessible,Note) VALUES
('12',48,1,'Lift equipped'),('27',54,0,NULL);

INSERT INTO sb_route (SchoolID,Name,TripType,BusID,DriverID,StartTime) VALUES
(1,'North Woods Morning','Morning',1,1,'07:05:00'),
(1,'North Woods Afternoon','Afternoon',1,2,'15:10:00');

INSERT INTO sb_route_stop (RouteID,SequenceNumber,StopName,Address,StopTime) VALUES
(1,1,'Maple and First','1 Maple Street','07:15:00'),
(1,2,'Community Library','25 Cedar Avenue','07:25:00'),
(1,3,'Pine Valley Elementary','100 Learning Lane','07:40:00'),
(2,1,'Pine Valley Elementary','100 Learning Lane','15:10:00'),
(2,2,'Community Library','25 Cedar Avenue','15:25:00'),
(2,3,'Maple and First','1 Maple Street','15:35:00');

INSERT INTO sb_student (FirstName,LastName,Grade,EmergencyPhone,RouteStopID,Note) VALUES
('Avery','Bennett','3','5550104001',1,NULL),
('Jordan','Kim','4','5550104002',2,'Allergy information held by school office'),
('Riley','Patel','2','5550104003',1,NULL);
