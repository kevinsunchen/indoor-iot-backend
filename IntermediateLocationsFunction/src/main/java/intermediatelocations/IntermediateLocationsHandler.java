package intermediatelocations;

import static intermediatelocations.IntermediateLocationsUtils.*;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.DynamodbEvent;
import com.amazonaws.services.lambda.runtime.events.DynamodbEvent.DynamodbStreamRecord;
import com.amazonaws.services.lambda.runtime.events.models.dynamodb.AttributeValue;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

import com.amazonaws.services.dynamodbv2.AmazonDynamoDB;
import com.amazonaws.services.dynamodbv2.AmazonDynamoDBClientBuilder;
import com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapper;
import com.amazonaws.services.dynamodbv2.document.DynamoDB;
import com.amazonaws.services.dynamodbv2.document.Item;
import com.amazonaws.services.dynamodbv2.document.ItemCollection;
import com.amazonaws.services.dynamodbv2.document.QueryOutcome;
import com.amazonaws.services.dynamodbv2.document.Table;
import com.amazonaws.services.dynamodbv2.document.spec.QuerySpec;
import com.amazonaws.services.dynamodbv2.document.utils.ValueMap;


/**
 * Handler for requests to IntermediateLocationsFunction Lambda function.
 * 
 * https://docs.aws.amazon.com/lambda/latest/dg/with-ddb.html
 * 
 * Measurement Data
 *  - EPC: tag id, string
 *  - Channel Estimates: 14 complex 64-bit numbers (currently stored as binary string in pickle format but open to better ways of doing this) 
 *      - Array: [[float_real1, float_imag1], [float_real2, float_imag2],...]
 *      - Complex a + bi = [a, b]
 *  - Timestamp: Millisecond epoch time stored as 13-digit number i.e. ‘1643179964390’ (TODO: change to millisecond epoch time in schema)
 *  - Device_id: id of updater device taking measurements, string
 *  - Area_id: id of mapped area, int
 *
 * Location Data of Device
 *  - Pose: 6D pose (x,y,z, qx,qy,qz,qw) of updater, each number is float
 *      - {‘x’: 1.2, ‘y’: 3.5, …}
 *  - Timestamp: Millisecond epoch time stored as 13-digit number i.e. ‘1643179964390’ (TODO: change to millisecond epoch time in schema)
 *  - Device id: id of updater device getting the location, string
 *  - Area_id: id of mapped area, int

 */
public class IntermediateLocationsHandler implements RequestHandler<DynamodbEvent, String> {
    final AmazonDynamoDB client = AmazonDynamoDBClientBuilder.standard().build();
    final int TIME_WINDOW_MS = 10;

    public String handleRequest(final DynamodbEvent ddbEvent, final Context context) {
        DynamoDB dynamoDB = new DynamoDB(client);
        Table updaterTable = dynamoDB.getTable(UPDATER_TABLE);

        // Create mapper item to save items using object persistence interface (used for IntermediateLocationsQueue)
        DynamoDBMapper mapper = new DynamoDBMapper(client);
        
        for (DynamodbStreamRecord measurementRecord : ddbEvent.getRecords()) {
            System.out.println(measurementRecord.getEventID() + "; " + measurementRecord.getEventName());

            if (measurementRecord.getEventName().equals(INSERT)) {
                System.out.println("Insert operation detected");
                Map<String, AttributeValue> measItem = measurementRecord.getDynamodb().getNewImage();
                System.out.println(measItem);

                // Get epc as String
                String epc = measItem.get(EPC).getS();
                // Get device id as String
                String deviceId = measItem.get(DEVICE_ID).getS();
                // Get timestamp as millisecond epoch time stored as Number, converted to long
                long measTimestamp = Long.parseLong(measItem.get("Timestamp").getN());
                System.out.println(DEVICE_ID + ": " + deviceId + "; " + TIMESTAMP + ": " + measTimestamp + "; " + EPC + ": " + epc);

                // Query for updater positions with corresponding device ID and timestamp within +/-10ms of measurement timestamp 
                QuerySpec updaterQuerySpec = new QuerySpec()
                    .withKeyConditionExpression(DEVICE_ID + " = :v_device_id and (" + TIMESTAMP + " between :v_time_lowerbound and :v_time_higherbound)")
                    .withValueMap(new ValueMap()
                        .withString(":v_device_id", deviceId)
                        .withNumber(":v_time_lowerbound", measTimestamp - TIME_WINDOW_MS)
                        .withNumber(":v_time_higherbound", measTimestamp + TIME_WINDOW_MS))
                    .withConsistentRead(true);
                
                ItemCollection<QueryOutcome> updaterItems = updaterTable.query(updaterQuerySpec);
                Iterator<Item> iterator = updaterItems.iterator();
                // Initialize running tracker of most recent updater item
                Item mostRecentUpdaterItem = iterator.next();
                System.out.println(mostRecentUpdaterItem.toJSONPretty());
                while (iterator.hasNext()) {
                    Item nextUpdaterItem = iterator.next();
                    System.out.println(nextUpdaterItem.toJSONPretty());
                    if (nextUpdaterItem.getLong(TIMESTAMP) > mostRecentUpdaterItem.getLong(TIMESTAMP)) {
                        mostRecentUpdaterItem = nextUpdaterItem;
                    }
                }

                // Create new item for IntermediateLocationsQueue, fill it with aggregated information
                // from measurement data and updater position, and save it to table
                IntermediateLocationItem intLocItem = new IntermediateLocationItem();
                intLocItem.setDeviceId(deviceId);
                intLocItem.setEpc(epc);
                intLocItem.setTimestamp(measTimestamp);
                intLocItem.setAreaId(measItem.get(AREA_ID).getS());
                intLocItem.setUpdaterPose(mostRecentUpdaterItem.getMap(UPDATER_POSE));
                intLocItem.setChannelEstimates(convertChannelEstimates(measItem.get(CHANNEL_ESTIMATES).getL()));

                mapper.save(intLocItem); 
            }
        }
     
        return "";
    }



}
