-- ---------------------------------------------------------------------
-- Scholarship Database Schema
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `Student` (
  `Student_ID` char(15) NOT NULL,
  `Scholarship_Type` varchar(50) NOT NULL,
  `Scholar_Classification` varchar(50) NOT NULL,
  `Name` varchar(100) NOT NULL,
  `Landline` varchar(15) DEFAULT NULL,
  `Mobile_Number` varchar(15) DEFAULT NULL,
  `Email_Address` varchar(100) DEFAULT NULL,
  `College_Enrolled` varchar(150) NOT NULL,
  `Program` varchar(100) NOT NULL,
  `Year_and_Section` varchar(20) NOT NULL,
  `Address` varchar(255) NOT NULL,
  `Date_of_Birth` date DEFAULT NULL,
  `Age` int DEFAULT NULL,
  `Civil_Status` char(20) NOT NULL,
  `Citizenship` char(50) NOT NULL,
  `Religion` char(50) DEFAULT NULL,
  `Working_Student` tinyint(1) DEFAULT '0',
  `Job_Title` varchar(100) DEFAULT NULL,
  `Other_Scholarship` varchar(250) DEFAULT NULL,
  `Grade_11_GWA` decimal(5,2) DEFAULT NULL,
  `Grade_12_GWA` decimal(5,2) DEFAULT NULL,
  `House_Ownership` char(50) DEFAULT NULL,
  `Total_Annual_Household_Income` decimal(9,2) DEFAULT NULL,
  `Family_own_a_vehicle` tinyint(1) DEFAULT '0',
  `COR` varchar(100) DEFAULT NULL,
  `CTC` varchar(100) DEFAULT NULL,
  `FORM137` varchar(100) DEFAULT NULL,
  `Proof_of_Income` varchar(100) NOT NULL,
  PRIMARY KEY (`Student_ID`),
  UNIQUE KEY `Email_Address` (`Email_Address`),
  CONSTRAINT `student_chk_1` CHECK ((`Scholarship_Type` in ('Financial Aid','Merit'))),
  CONSTRAINT `student_chk_2` CHECK ((`Scholar_Classification` in ('Freshmen','Upperclassman'))),
  CONSTRAINT `student_chk_3` CHECK ((`Age` >= 16 and `Age` <= 99)),
  CONSTRAINT `student_chk_4` CHECK ((`Total_Annual_Household_Income` >= 0.00 and `Total_Annual_Household_Income` <= 1000000.00)),
  CONSTRAINT `student_chk_5` CHECK (((`Scholar_Classification` = 'Freshmen' and `FORM137` is not null and `Grade_11_GWA` is not null and `Grade_12_GWA` is not null) or (`Scholar_Classification` = 'Upperclassman' and `COR` is not null and `CTC` is not null)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `Family` (
  `Family_ID` int NOT NULL AUTO_INCREMENT,
  `Student_ID` char(15) DEFAULT NULL,
  `Member_Role` varchar(50) NOT NULL,
  `Member_Name` varchar(100) NOT NULL,
  `Member_Age` int DEFAULT NULL,
  `Member_Mobile_Number` char(11) DEFAULT NULL,
  `Member_Civil_Status` varchar(20) DEFAULT NULL,
  `Member_Employed` tinyint(1) DEFAULT '0',
  `Member_Course_or_Occupation` varchar(100) DEFAULT NULL,
  `Member_School_or_Employer` varchar(100) DEFAULT NULL,
  `Member_Department` varchar(100) DEFAULT NULL,
  `Member_Position` varchar(100) DEFAULT NULL,
  `Member_With_Own_Business` tinyint(1) DEFAULT '0',
  `Member_Office_or_Business_Name_Address` varchar(300) DEFAULT NULL,
  `Member_Monthly_Income` decimal(10,2) DEFAULT '0.00',
  PRIMARY KEY (`Family_ID`),
  KEY `fk_family_student` (`Student_ID`),
  CONSTRAINT `fk_family_student` FOREIGN KEY (`Student_ID`) REFERENCES `Student` (`Student_ID`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `family_chk_1` CHECK ((`Member_Role` in ('Father','Mother','Sibling','Relative'))),
  CONSTRAINT `family_chk_2` CHECK ((`Member_Age` >= 0 and `Member_Age` <= 99)),
  CONSTRAINT `family_chk_3` CHECK ((`Member_Civil_Status` is null or `Member_Civil_Status` in ('Single','Married','Widowed','Divorced','Separated'))),
  CONSTRAINT `family_chk_4` CHECK ((`Member_Monthly_Income` is null or `Member_Monthly_Income` >= 0.00)),
  CONSTRAINT `family_chk_5` CHECK ((`Member_Mobile_Number` is null or (length(`Member_Mobile_Number`) = 11 and `Member_Mobile_Number` like '09%')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin AUTO_INCREMENT=150001;

CREATE TABLE IF NOT EXISTS `School` (
  `School_ID` int NOT NULL AUTO_INCREMENT,
  `History_Education_Level` varchar(50) DEFAULT NULL,
  `Student_ID` char(15) DEFAULT NULL,
  `School_Name` varchar(100) NOT NULL,
  `School_Address` varchar(255) NOT NULL,
  `School_From` year(4) DEFAULT NULL,
  `School_To` year(4) DEFAULT NULL,
  `School_Honors` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`School_ID`),
  UNIQUE KEY `unique_studenteduc` (`Student_ID`,`History_Education_Level`),
  CONSTRAINT `fk_school_student` FOREIGN KEY (`Student_ID`) REFERENCES `Student` (`Student_ID`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `school_chk_1` CHECK ((`History_Education_Level` in ('Primary','Secondary','Other Institution'))),
  CONSTRAINT `school_chk_2` CHECK ((`School_To` >= `School_From`))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin AUTO_INCREMENT=120001;

CREATE TABLE IF NOT EXISTS `Extra_Curricular` (
  `Extra_Curricular_ID` int NOT NULL AUTO_INCREMENT,
  `Student_ID` char(15) DEFAULT NULL,
  `Extra_Curricular_Year` char(9) DEFAULT NULL,
  `Extra_Curricular_Name` varchar(100) DEFAULT NULL,
  `Extra_Curricular_Position` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`Extra_Curricular_ID`),
  KEY `fk_extracur_student` (`Student_ID`),
  CONSTRAINT `fk_extracur_student` FOREIGN KEY (`Student_ID`) REFERENCES `Student` (`Student_ID`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `extra_curricular_chk_1` CHECK ((`Extra_Curricular_Year` is null or `Extra_Curricular_Year` regexp '^[0-9]{4}-[0-9]{4}$'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin AUTO_INCREMENT=120001;
