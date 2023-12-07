/*
Cooperative IOT Self Organizing Example
SwitchDoc Labs, August 2015

 */

#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <Adafruit_NeoPixel.h>


#undef DEBUG

char ssid[] = "NETGEAR21";  //  your network SSID (name)
char pass[] = "greenunicorn576";       // your network password


#define VERSIONNUMBER 28


#define LOGGERIPINC 20
#define SWARMSIZE 5
// 3 seconds is too old - it must be dead
#define SWARMTOOOLD 5000

int mySwarmID = 0;

// Packet Types

#define LIGHT_UPDATE_PACKET 0
#define RESET_SWARM_PACKET 1
#define CHANGE_TEST_PACKET 2
#define RESET_ME_PACKET 3
#define DEFINE_SERVER_LOGGER_PACKET 4
#define LOG_TO_SERVER_PACKET 5
#define MASTER_CHANGE_PACKET 6
#define BLINK_BRIGHT_LED 7
#define LOG_DATA_PACKET 8



unsigned int localPort = 2910;      // local port to listen for UDP packets

// master variables
boolean masterState = true;   // True if master, False if not
int swarmClear[SWARMSIZE];
int swarmVersion[SWARMSIZE];
int swarmState[SWARMSIZE];
long swarmTimeStamp[SWARMSIZE];   // for aging

IPAddress serverAddress = IPAddress(0, 0, 0, 0); // default no IP Address




int swarmAddresses[SWARMSIZE];  // Swarm addresses




int size,times,pin2;
int pin = D2;
int clearColor;

const int PACKET_SIZE = 14; // Light Update Packet
const int BUFFERSIZE = 1024;

byte packetBuffer[BUFFERSIZE]; //buffer to hold incoming and outgoing packets

// A UDP instance to let us send and receive packets over UDP
WiFiUDP udp;
IPAddress localIP;

//
#define LEDS_COUNT 8
Adafruit_NeoPixel strip = Adafruit_NeoPixel(LEDS_COUNT,pin, NEO_GRB + NEO_KHZ800);

void handleLogDataPacket(byte* data) {
  // 读取相关信息
  byte historyMasterLen = data[2];
  byte historyTimeLen = data[3];
  byte historyValueLen = data[4];


  // 打印 history_master 数组
  Serial.print("history_master: ");
  for (int i = 5; i < 5 + 2*historyMasterLen; i+=2) {
    Serial.print(data[i]+data[i+1]*256);
    Serial.print(" ");
  }
  Serial.println();

  // 打印 history_time 数组
  Serial.print("history_time: ");
  for (int i = 5 + 2*historyMasterLen; i < 5 + 2*historyMasterLen + 2*historyTimeLen; i+=2) {
    Serial.print(data[i]+data[i+1]*256);
    Serial.print(" ");
  }
  Serial.println();

  // 打印 history_value 数组
  Serial.print("history_value: ");
  for (int i = 5 + 2*historyMasterLen + 2*historyTimeLen; i < 5 + 2*historyMasterLen + 2*historyTimeLen + 2*historyValueLen; i+=2) {
    Serial.print(data[i]+data[i+1]*256);
    Serial.print(" ");
  }
  Serial.println();
}




int getV(){
  int sensorValue = analogRead(A0);
  return sensorValue;
}

void analogLED() {
  int lightValue = getV();
  
  // 映射光强度到颜色渐变
  int color = map(lightValue, 0, 1023, 0, 255);
  
  // 设置LED颜色
  for (int i = 0; i < LEDS_COUNT; i++) {
    strip.setPixelColor(i, strip.Color(color, 255 - color, 0)); // 在这里可以调整颜色，这里是从红到绿的渐变
  }
  //Serial.print("The reading is:");
  //Serial.println(lightValue);
  //Serial.print("The color is:");
  //Serial.println(color);
  // 显示颜色
  strip.show();
}



void setup()
{

  pin2 = 2;
  strip.begin();
  strip.show();
  pinMode(pin2, OUTPUT);
  digitalWrite(pin2, LOW);
  Serial.begin(115200);
  Serial.println();
  Serial.println();



  Serial.println("");
  Serial.println("--------------------------");
  Serial.println("LightSwarm");
  Serial.print("Version ");
  Serial.println(VERSIONNUMBER);
  Serial.println("--------------------------");

  Serial.println(F(" 09/03/2015"));
  Serial.print(F("Compiled at:"));
  Serial.print (F(__TIME__));
  Serial.print(F(" "));
  Serial.println(F(__DATE__));
  Serial.println();
  pinMode(0, OUTPUT);

  digitalWrite(0, LOW);
  delay(500);
  digitalWrite(0, HIGH);

  randomSeed(analogRead(A0));
  Serial.print("analogRead(A0)=");
  Serial.println(analogRead(A0));




  // everybody starts at 0 and changes from there
  mySwarmID = 0;

  // We start by connecting to a WiFi network
  Serial.print("LightSwarm Instance: ");
  Serial.println(mySwarmID);

  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, pass);
 

  // initialize Swarm Address - we start out as swarmID of 0
  

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");

  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());

  Serial.println("Starting UDP");

  udp.begin(localPort);
  Serial.print("Local port: ");
  Serial.println(udp.localPort());



  // initialize light sensor and arrays
  int i;
  for (i = 0; i < SWARMSIZE; i++)
  {

    swarmAddresses[i] = 0;
    swarmClear[i] = 0;
    swarmTimeStamp[i] = -1;
  }
  swarmClear[mySwarmID] = 0;
  swarmTimeStamp[mySwarmID] = 1;   // I am always in time to myself
  clearColor = swarmClear[mySwarmID];
  swarmVersion[mySwarmID] = VERSIONNUMBER;
  swarmState[mySwarmID] = masterState;
  Serial.print("clearColor =");
  Serial.println(clearColor);


  // set SwarmID based on IP address 

  
  localIP = WiFi.localIP();
  
  swarmAddresses[0] =  localIP[3];
  
  
  mySwarmID = 0;
  
  Serial.print("MySwarmID=");
  Serial.println(mySwarmID);

}

void loop()
{
  int secondsCount;
  int lastSecondsCount;

  lastSecondsCount = 0;
#define LOGHOWOFTEN
  secondsCount = millis() / 100;
  // wait to see if a reply is available
  delay(300);

  int cb = udp.parsePacket();
  swarmClear[mySwarmID] = getV();
  broadcastARandomUpdatePacket();
  if (!cb) {
    //  Serial.println("no packet yet");
    Serial.print(".");
  }
  else {
    // We've received a packet, read the data from it

    udp.read(packetBuffer, 500); // read the packet into the buffer
    Serial.print("packetbuffer[1] =");
    Serial.println(packetBuffer[1]);
    Serial.print("PACKET SIZE IS ");
    Serial.println(500);
    if(packetBuffer[1] == LOG_DATA_PACKET)
    {
      // 在这里接收 UDP 数据到 packetBuffer
      // 处理接收到的数据包裹
      handleLogDataPacket(packetBuffer);
    }
    if (packetBuffer[1] == LIGHT_UPDATE_PACKET)
    {
      Serial.print("LIGHT_UPDATE_PACKET received from LightSwarm #");
      Serial.println(packetBuffer[2]);
      setAndReturnMySwarmIndex(packetBuffer[2]);

      Serial.print("LS Packet Recieved from #");
      Serial.print(packetBuffer[2]);
      Serial.print(" SwarmState:");
      if (packetBuffer[3] == 0)
        Serial.print("SLAVE");
      else
        Serial.print("MASTER");
      Serial.print(" Version=");
      Serial.println(packetBuffer[4]);

      // record the incoming clear color

      swarmClear[setAndReturnMySwarmIndex(packetBuffer[2])] = packetBuffer[5] * 256 + packetBuffer[6];
      swarmVersion[setAndReturnMySwarmIndex(packetBuffer[2])] = packetBuffer[4];
      swarmState[setAndReturnMySwarmIndex(packetBuffer[2])] = packetBuffer[3];
      swarmTimeStamp[setAndReturnMySwarmIndex(packetBuffer[2])] = millis();


      // Check to see if I am master!
      checkAndSetIfMaster();

    }

    if (packetBuffer[1] == RESET_SWARM_PACKET)
    {
      Serial.println(">>>>>>>>>RESET_SWARM_PACKETPacket Recieved");
      masterState = true;
      Serial.println("Reset Swarm:  I just BECAME Master (and everybody else!)");
      //digitalWrite(0, LOW);
      digitalWrite(pin2,HIGH);
      delay(3000);
      setup();
    }
  }
    
  if (packetBuffer[1] ==  DEFINE_SERVER_LOGGER_PACKET)
  {
    Serial.println(">>>>>>>>>DEFINE_SERVER_LOGGER_PACKET Packet Recieved");
    serverAddress = IPAddress(packetBuffer[4], packetBuffer[5], packetBuffer[6], packetBuffer[7]);
    Serial.print("Server address received: ");
    Serial.println(serverAddress);
  }
  Serial.print("MasterStatus:");
  if (masterState == true)
  {
    //digitalWrite(0, LOW);
    digitalWrite(pin2,LOW);
    Serial.print("MASTER");
  }
  else
  {
    //digitalWrite(0, HIGH);
    digitalWrite(pin2,HIGH);
    Serial.print("SLAVE");
  }
  Serial.print("/cc=");
  Serial.print(clearColor);
  Serial.print("/KS:");
  Serial.println(serverAddress);
  
  Serial.println("--------");
  
  
  int i;
  for (i = 0; i < SWARMSIZE; i++)
  {
    Serial.print("swarmAddress[");
    Serial.print(i);
    Serial.print("] = ");
    Serial.println(swarmAddresses[i]); 
  }
  Serial.println("--------");
  
  
  //broadcastARandomUpdatePacket();
  delay(100);
  analogLED();
  delay(1000);
  //  sendARandomUpdatePacket();
  swarmClear[mySwarmID] = getV();
  sendLogToServer(swarmClear[mySwarmID]);

}
// send an LIGHT Packet request to the swarms at the given address
void sendLightUpdatePacket(IPAddress & address)
{

  //Serial.print("sending Light Update packet to:");
  // Serial.println(address);

  int clearColor = getV();
  printf("%i\n",clearColor);
  // Initialize values needed to form Light Packet
  // (see URL above for details on the packets)
  packetBuffer[0] = 0xF0;   // StartByte
  packetBuffer[1] = LIGHT_UPDATE_PACKET;     // Packet Type
  packetBuffer[2] = localIP[3];     // Sending Swarm Number
  packetBuffer[3] = masterState;  // 0 = slave, 1 = master
  packetBuffer[4] = VERSIONNUMBER;  // Software Version
  packetBuffer[5] = (clearColor & 0xFF00) >> 8; // Clear High Byte
  packetBuffer[6] = (clearColor & 0x00FF); // Clear Low Byte
  packetBuffer[7] =  0;
  packetBuffer[8] =  0;
  packetBuffer[9] =  0;
  packetBuffer[10] = 0;
  packetBuffer[11] = 0;
  packetBuffer[12] = 0;
  packetBuffer[13] = 0x0F;  //End Byte

  //printf("now is getV works!\n");
  printf("Value: %i\n", getV());
  printf("the original clearcolor is : %i\n", packetBuffer[5] * 256 + packetBuffer[6]);

  // all Light Packet fields have been given values, now
  // you can send a packet requesting coordination
  udp.beginPacketMulticast(address,  localPort, WiFi.localIP()); //
  //udp.beginPacket(address,  localPort); //
  udp.write(packetBuffer, PACKET_SIZE);
  udp.endPacket();
  //check if send out
  //Serial.println("I have broadcast light update package");
}

// delay 0-MAXDELAY ms
#define MAXDELAY 300
void broadcastARandomUpdatePacket()
{

  int sendToLightSwarm = 255;
  Serial.print("Broadcast ToSwarm = ");
  Serial.print(sendToLightSwarm);
  Serial.print(" ");

  // delay 0-MAXDELAY seconds
  int randomDelay;
  randomDelay = random(100, MAXDELAY);
  Serial.print("Delay = ");
  Serial.print(randomDelay);
  Serial.print("ms : ");

  delay(randomDelay);

  IPAddress sendSwarmAddress(192, 168, 1, sendToLightSwarm); // my Swarm Address
  sendLightUpdatePacket(sendSwarmAddress);




}


void checkAndSetIfMaster()
{

  int i;
  for (i = 0; i < SWARMSIZE; i++)
  {


#ifdef DEBUG

    Serial.print("swarmClear[");
    Serial.print(i);
    Serial.print("] = ");
    Serial.print(swarmClear[i]);
    Serial.print("  swarmTimeStamp[");
    Serial.print(i);
    Serial.print("] = ");
    Serial.println(swarmTimeStamp[i]);
#endif

    Serial.print("#");
    Serial.print(i);
    Serial.print("/");
    Serial.print(swarmState[i]);
    Serial.print("/");
    Serial.print(swarmVersion[i]);
    Serial.print(":");
    // age data
    int howLongAgo = millis() - swarmTimeStamp[i] ;

    if (swarmTimeStamp[i] == 0)
    {
      Serial.print("TO ");
    }
    else if (swarmTimeStamp[i] == -1)
    {
      Serial.print("NP ");
    }
    else if (swarmTimeStamp[i] == 1)
    {
      Serial.print("ME ");
    }
    else if (howLongAgo > SWARMTOOOLD)
    {
      Serial.print("TO ");
      swarmTimeStamp[i] = 0;
      swarmClear[i] = 0;

    }
    else
    {
      Serial.print("PR ");


    }
  }

  Serial.println();
  boolean setMaster = true;

  for (i = 0; i < SWARMSIZE; i++)
  {

    if (swarmClear[mySwarmID] >= swarmClear[i])
    {
      // I might be master!

    }
    else
    {
      // nope, not master
      setMaster = false;
      break;
    }

  }
  if (setMaster == true)
  {
    if (masterState == false)
    {
      Serial.println("I just BECAME Master");
      //digitalWrite(0, HIGH);
      digitalWrite(pin2, LOW);
    }

    masterState = true;
  }
  else
  {
    if (masterState == true)
    {
      Serial.println("I just LOST Master");
      //digitalWrite(0, HIGH);
      digitalWrite(pin2, HIGH);
    }

    masterState = false;
  }

  swarmState[mySwarmID] = masterState;

}


int setAndReturnMySwarmIndex(int incomingID)
{
 
  int i;
  for (i = 0; i< SWARMSIZE; i++)
  {
    if (swarmAddresses[i] == incomingID)
    {
       return i;
    } 
    else
    if (swarmAddresses[i] == 0)  // not in the system, so put it in
    {
    
      swarmAddresses[i] = incomingID;
      Serial.print("incomingID ");
      Serial.print(incomingID);
      Serial.print("  assigned #");
      Serial.println(i);
      return i;
    }
    
  }  
  
  // if we get here, then we have a new swarm member.   
  // Delete the oldest swarm member and add the new one in 
  // (this will probably be the one that dropped out)
  
  int oldSwarmID;
  long oldTime;
  oldTime = millis();
  for (i = 0;  i < SWARMSIZE; i++)
 {
  if (oldTime > swarmTimeStamp[i])
  {
    oldTime = swarmTimeStamp[i];
    oldSwarmID = i;
  }
  
 } 
 
 // remove the old one and put this one in....
 swarmAddresses[oldSwarmID] = incomingID;
 // the rest will be filled in by Light Packet Receive
 return -1;
  
}


// send log packet to Server if master and server address defined

void sendLogToServer(int voltage)
{

  // build the string

  char myBuildString[1000];
  myBuildString[0] = '\0';
  delay(500);
  if (masterState == true)
  {
    // now check for server address defined
    if ((serverAddress[0] == 0) && (serverAddress[1] == 0))
    {
      return;  // we are done.  not defined
    }
    else
    {
      // now send the packet as a string with the following format:
      // swarmID, MasterSlave, SoftwareVersion, clearColor, Status | ....next Swarm ID
      // 0,1,15,3883, PR | 1,0,14,399, PR | ....



      int i;
      char swarmString[20];
      swarmString[0] = '\0';

      for (i = 0; i < SWARMSIZE; i++)
      {

        char stateString[5];
        stateString[0] = '\0';
        if (swarmTimeStamp[i] == 0)
        {
          strcat(stateString, "TO");
        }
        else if (swarmTimeStamp[i] == -1)
        {
          strcat(stateString, "NP");
        }
        else if (swarmTimeStamp[i] == 1)
        {
          strcat(stateString, "PR");
        }
        else
        {
          strcat(stateString, "PR");
        }

        sprintf(swarmString, " %i,%i,%i,%i,%s,%i ", i, swarmState[i], swarmVersion[i], swarmClear[i], stateString, swarmAddresses[i]);

        strcat(myBuildString, swarmString);
        if (i < SWARMSIZE - 1)
        {

          strcat(myBuildString, "|");

        }
      }


    }


    // set all bytes in the buffer to 0
    memset(packetBuffer, 0, BUFFERSIZE);
    // Initialize values needed to form Light Packet
    // (see URL above for details on the packets)
    packetBuffer[0] = 0xF0;   // StartByte
    packetBuffer[1] = LOG_TO_SERVER_PACKET;     // Packet Type
    packetBuffer[2] = localIP[3];     // Sending Swarm Number
    packetBuffer[3] = strlen(myBuildString); // length of string in bytes
    packetBuffer[4] = VERSIONNUMBER;  // Software Version
    packetBuffer[5] = (voltage & 0xFF00) >> 8; // Clear High Byte
    packetBuffer[6] = (voltage & 0x00FF); // Clear Low Byte
    int i;
    for (i = 0; i < strlen(myBuildString); i++)
    {
      packetBuffer[i + 7] = myBuildString[i];// first string byte
    }

    packetBuffer[i + 7] = 0x0F; //End Byte
    Serial.print("Sending Log to Sever:");
    Serial.println(myBuildString);
    int packetLength;
    packetLength = i + 7 + 1;

    udp.beginPacket(serverAddress,  localPort); //

    udp.write(packetBuffer, packetLength);
    udp.endPacket();
    //test if sendout
    Serial.println("I have send log to server but not sure if it receives my package.");

  }



}

