package intermediatelocations;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URL;
import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.DynamodbEvent;
import com.amazonaws.services.lambda.runtime.events.DynamodbEvent.DynamodbStreamRecord;
import com.amazonaws.services.dynamodbv2.AmazonDynamoDB;
import com.amazonaws.services.dynamodbv2.AmazonDynamoDBClientBuilder;


/**
 * Handler for requests to IntermediateLocationsFunction Lambda function.
 * 
 * https://docs.aws.amazon.com/lambda/latest/dg/with-ddb.html
 */
public class IntermediateLocationsHandler implements RequestHandler<DynamodbEvent, String> {
    static final String INSERT = "INSERT";
    static final String MODIFY = "MODIFY";
    static final String REMOVE = "REMOVE";
    static AmazonDynamoDB client = AmazonDynamoDBClientBuilder.standard().build();

    public String handleRequest(final DynamodbEvent ddbEvent, final Context context) {
        
        System.out.println("Hello");
        for (DynamodbStreamRecord record : ddbEvent.getRecords()) {
            System.out.println(record.getEventID());
            System.out.println(record.getEventName());
            // System.out.println(record.getDynamodb().toString() + "\n");
            System.out.println(record.getDynamodb().getNewImage() + "\n");
            if (record.getEventName().equals(INSERT)) {
                System.out.println("Insert operation performed");
            }
        }
        return "";
    }


}
